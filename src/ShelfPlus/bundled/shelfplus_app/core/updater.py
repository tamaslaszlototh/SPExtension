"""Self-update from GitHub Releases (PRD R9).

Pure Python: no Qt, no ``substance_painter``. The network sits behind a small
interface, so tests drive the whole flow with a fake:

- ``network.get(url, on_done, accept=None) -> handle``: an asynchronous GET that follows
  redirects (GitHub's asset links answer 302) and sends a ``User-Agent``. It calls
  ``on_done(Response)`` exactly once, unless ``handle.abort()`` was called first.

The flow:

1. **Check** ``releases/latest`` on start at most every 24 h (``lastCheck`` in
   ``panel.json``), or whenever the user asks. Pre-releases and drafts are ignored.
2. A newer version that is not skipped, not marked bad by the loader and not installed
   yet is **offered**: ``ui.offer(Offer)`` with Update / Later / Skip this version. If
   its ``min_loader`` (the release's ``VERSION`` asset) is newer than the running
   loader, the offer is a manual reinstall instead and nothing is downloaded.
3. **Update** downloads ``SHA256SUMS`` and the zip into a staging folder, verifies the
   SHA-256, unpacks ``bundled/`` and ``VERSION`` into ``versions/.staging-<v>``, and
   renames that to ``versions/<v>`` last. The loader starts it the next time Painter
   starts; nothing running is replaced. Versions beyond the two newest are deleted.

Errors: silent (logged) on the start-up check, every one shown on a manual check, and a
message when an update fails, after which the staging folders are deleted.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

log = logging.getLogger("ShelfPlus.app.updater")

REPO = "tamaslaszlototh/SPExtension"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"
API_ACCEPT = "application/vnd.github+json"
CHECK_INTERVAL = 24 * 60 * 60  # seconds between start-up checks
KEEP_VERSIONS = 2
APP_PACKAGE = "shelfplus_app"
ZIP_ROOT = "ShelfPlus/"
SUMS_ASSET = "SHA256SUMS"
VERSION_ASSET = "VERSION"

UPDATED_MESSAGE = "Update downloaded; it will be active the next time Painter starts."

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


class UpdateError(Exception):
    """A check or an update failed; the text is shown to the user."""


class NeedsReinstall(UpdateError):
    """The release needs a newer loader than the one installed."""


# -- versions -------------------------------------------------------------------


def parse_version(text):
    """``"1.2.3"`` -> ``(1, 2, 3)``; anything else -> ``None``."""
    match = _VERSION_RE.match(text) if isinstance(text, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def is_newer(candidate, current):
    """Whether version ``candidate`` is newer than ``current``. Unparsable -> False."""
    a, b = parse_version(candidate), parse_version(current)
    return a is not None and b is not None and a > b


def check_due(last_check, now, interval=CHECK_INTERVAL):
    """The 24 h throttle of the start-up check. A missing or future time is due."""
    if not isinstance(last_check, (int, float)) or isinstance(last_check, bool):
        return True
    return not (0 <= now - last_check < interval)


def read_bad_versions(data_dir):
    """The versions the loader has marked bad (``loader.json``)."""
    try:
        data = json.loads((Path(data_dir) / "loader.json").read_text(encoding="utf-8"))
        return [v for v in data.get("bad_versions", []) if isinstance(v, str)]
    except (OSError, ValueError, AttributeError):
        return []


def read_version_info(text):
    """A ``VERSION`` file's text -> ``(version, min_loader)``; raises ``UpdateError``."""
    try:
        data = json.loads(text)
        version = data["version"]
        min_loader = data.get("min_loader", 1)
    except (ValueError, KeyError, TypeError, AttributeError):
        raise UpdateError("its VERSION file cannot be read") from None
    if parse_version(version) is None or not isinstance(min_loader, int) or isinstance(min_loader, bool):
        raise UpdateError("its VERSION file cannot be read")
    return version, min_loader


# -- the release ----------------------------------------------------------------


@dataclass
class Release:
    version: str
    tag: str
    notes: str
    page_url: str
    zip_name: str
    zip_url: str = None
    sums_url: str = None
    version_url: str = None


def parse_release(data):
    """GitHub's ``releases/latest`` JSON -> ``Release``, or ``None`` for a pre-release,
    a draft, or a tag that is not ``vX.Y.Z``. Raises ``UpdateError`` if it is not a release."""
    if not isinstance(data, dict) or not isinstance(data.get("tag_name"), str):
        raise UpdateError("GitHub's answer is not a release")
    if data.get("prerelease") or data.get("draft"):
        return None
    match = _TAG_RE.match(data["tag_name"])
    if not match:
        return None
    tag = data["tag_name"]
    release = Release(
        version=match.group(1),
        tag=tag,
        notes=data.get("body") if isinstance(data.get("body"), str) else "",
        page_url=data.get("html_url") if isinstance(data.get("html_url"), str) else f"{RELEASES_URL}/tag/{tag}",
        zip_name=f"ShelfPlus-{tag}.zip",
    )
    assets = data.get("assets") if isinstance(data.get("assets"), list) else []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name, url = asset.get("name"), asset.get("browser_download_url")
        if not isinstance(url, str):
            continue
        if name == release.zip_name:
            release.zip_url = url
        elif name == SUMS_ASSET:
            release.sums_url = url
        elif name == VERSION_ASSET:
            release.version_url = url
    return release


def parse_sums(text, file_name):
    """The SHA-256 of ``file_name`` in a ``SHA256SUMS`` file, lower case; raises ``UpdateError``."""
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[1].lstrip("*") == file_name and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    raise UpdateError(f"SHA256SUMS has no checksum for {file_name}")


def verify_sha256(path, expected):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected.lower():
        raise UpdateError("the download does not match its SHA-256 checksum")


# -- installing -----------------------------------------------------------------


def _member_target(name):
    """The path a zip member goes to inside the version folder, or ``None`` to skip it.

    Only ``ShelfPlus/bundled/…`` (the application) and ``ShelfPlus/VERSION`` are taken;
    the loader is installed by hand. A name that would leave the folder is refused.
    """
    if name == ZIP_ROOT + "VERSION":
        return PurePosixPath("VERSION")
    prefix = ZIP_ROOT + "bundled/"
    if not name.startswith(prefix) or name.endswith("/"):
        return None
    rel = PurePosixPath(name[len(prefix):])
    if not rel.parts or rel.is_absolute() or any(p in ("", ".", "..") or ":" in p or "\\" in p for p in rel.parts):
        raise UpdateError(f"the zip holds an unsafe path: {name}")
    return rel


def install_zip(zip_path, versions_dir, version, loader_version):
    """Unpack the release zip into ``versions_dir/<version>``.

    Everything goes into ``.staging-<version>`` first, which is renamed last, so a
    half-written version is never seen by the loader. The staging folder is deleted on
    failure. Raises ``NeedsReinstall`` if the zip needs a newer loader.
    """
    versions_dir = Path(versions_dir)
    target = versions_dir / version
    staging = versions_dir / (".staging-" + version)
    shutil.rmtree(staging, ignore_errors=True)
    try:
        try:
            archive = zipfile.ZipFile(zip_path)
        except (OSError, zipfile.BadZipFile):
            raise UpdateError("the download is not a zip file") from None
        with archive:
            try:
                info_text = archive.read(ZIP_ROOT + "VERSION").decode("utf-8")
            except (KeyError, UnicodeDecodeError):
                raise UpdateError("the zip has no ShelfPlus/VERSION") from None
            zip_version, min_loader = read_version_info(info_text)
            if zip_version != version:
                raise UpdateError(f"the zip holds v{zip_version}, not v{version}")
            if min_loader > loader_version:
                raise NeedsReinstall("This version needs a manual reinstall.")
            for member in archive.infolist():
                rel = _member_target(member.filename)
                if rel is None:
                    continue
                out = staging.joinpath(*rel.parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, open(out, "wb") as sink:
                    shutil.copyfileobj(source, sink)
        if not (staging / APP_PACKAGE / "__init__.py").is_file():
            raise UpdateError(f"the zip has no {APP_PACKAGE} package")
        if target.exists():
            raise UpdateError(f"v{version} is already installed")
        os.replace(staging, target)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(f"the zip is damaged ({exc})") from None
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(f"it could not be unpacked ({exc})") from None
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def installed_versions(versions_dir):
    """``[(version, min_loader)]`` of the installed versions, newest first."""
    found = []
    try:
        entries = list(Path(versions_dir).iterdir())
    except OSError:
        return []
    for entry in entries:
        if parse_version(entry.name) is None or not (entry / APP_PACKAGE / "__init__.py").is_file():
            continue
        try:
            version, min_loader = read_version_info((entry / "VERSION").read_text(encoding="utf-8"))
        except (OSError, UpdateError):
            version, min_loader = entry.name, 1
        found.append((entry.name, min_loader if version == entry.name else 1))
    found.sort(key=lambda item: parse_version(item[0]), reverse=True)
    return found


def apply_retention(versions_dir, bad_versions, loader_version, keep=(), count=KEEP_VERSIONS):
    """Delete the versions beyond the ``count`` newest good ones, the same rule as the
    loader's. Versions in ``keep`` (the running one) and versions that need a newer
    loader are left alone. Returns the deleted versions."""
    bad = set(bad_versions)
    installed = installed_versions(versions_dir)
    good = [v for v, min_loader in installed if v not in bad and min_loader <= loader_version]
    kept = set(good[:count]) | set(keep)
    removed = []
    for version, min_loader in installed:
        if version not in kept and min_loader <= loader_version:
            log.info("Removing old or bad v%s", version)
            shutil.rmtree(Path(versions_dir) / version, ignore_errors=True)
            removed.append(version)
    return removed


# -- the flow -------------------------------------------------------------------


@dataclass
class Response:
    status: int = None
    body: bytes = b""
    error: str = None  # set when the request itself failed (no network, timeout, …)


@dataclass
class Offer:
    """What the update dialog shows. ``reinstall``: the release needs a newer loader."""

    version: str
    current: str
    notes: str
    page_url: str
    reinstall: bool = False

    @property
    def text(self):
        text = f"Shelf+ v{self.version} is available (you have v{self.current})."
        if self.reinstall:
            text += (
                "\n\nThis version needs a manual reinstall: download its zip from the Releases page and "
                "copy the ShelfPlus folder into Painter's python\\plugins folder, replacing the old one."
            )
        return text


def _failure(response):
    """Why a response is not usable, or ``None`` if it is a success."""
    if response.status in (403, 429):
        return "GitHub's rate limit was reached; try again in an hour"
    if response.error:
        return response.error
    if response.status is None or not 200 <= response.status < 300:
        return f"GitHub answered with HTTP {response.status}"
    return None


class Updater:
    """The check and update flow. One at a time; ``close()`` ends it.

    ``state`` is ``panel.json``'s ``updater`` dict and ``save_state()`` writes it.
    ``ui`` has ``offer(Offer)`` (the non-blocking dialog), ``message(text)`` and
    ``busy(text or None)`` (a short status while checking or downloading).
    """

    def __init__(self, network, data_dir, version, loader_version, state, save_state, ui, clock=time.time):
        self.network = network
        self.data_dir = Path(data_dir)
        self.versions_dir = self.data_dir / "versions"
        self.version = version
        self.loader_version = loader_version
        self.state = state
        self.save_state = save_state
        self.ui = ui
        self.clock = clock
        self.offer = None  # the Offer on screen, with its Release in ``_offered``
        self._offered = None
        self._task = None  # "check" or "update" while one runs
        self._manual = False
        self._downloading = None  # the Release being downloaded
        self._request = None
        self._closed = False

    @property
    def busy(self):
        return self._task is not None

    # -- checking ------------------------------------------------------------------

    def check_on_start(self):
        """The start-up check, if 24 h have passed since the last one."""
        if not check_due(self.state.get("lastCheck"), self.clock()):
            log.info("Update check skipped: the last one was less than 24 h ago")
            return False
        self._check(manual=False)
        return True

    def check_now(self):
        """**Check for updates** in the Panel menu: no throttle, every result shown."""
        if self._task == "update":
            self.ui.message("An update is already downloading.")
            return
        if self._task == "check":
            self._manual = True  # the start-up check still runs; now its result is shown
            self.ui.busy("Checking for updates…")
            return
        self._check(manual=True)

    def _check(self, manual):
        self._task, self._manual = "check", manual
        self.state["lastCheck"] = self.clock()
        self.save_state()
        log.info("Checking for updates (%s)", "manual" if manual else "start-up")
        if manual:
            self.ui.busy("Checking for updates…")
        self._get(LATEST_URL, self._latest_received, accept=API_ACCEPT)

    def _latest_received(self, response):
        problem = _failure(response)
        if problem:
            return self._check_failed(problem)
        try:
            release = parse_release(json.loads(response.body.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            return self._check_failed("GitHub's answer cannot be read")
        except UpdateError as exc:
            return self._check_failed(str(exc))
        reason = self._not_offered(release)
        if reason is not None:
            return self._check_done(reason)
        if release.version_url is None:
            log.info("v%s has no VERSION asset; assuming min_loader 1", release.version)
            return self._offer(release, 1)
        self._get(release.version_url, lambda r: self._version_received(release, r))

    def _not_offered(self, release):
        """Why ``release`` is not offered (shown on a manual check), or ``None``."""
        current = f"Shelf+ v{self.version} is up to date."
        if release is None or not is_newer(release.version, self.version):
            return current
        if release.version in read_bad_versions(self.data_dir):
            log.info("v%s is marked bad; not offering it", release.version)
            return current
        if (self.versions_dir / release.version / APP_PACKAGE / "__init__.py").is_file():
            return f"Shelf+ v{release.version} is already downloaded; it will be active the next time Painter starts."
        if not self._manual and self.state.get("skippedVersion") == release.version:
            log.info("v%s is skipped; not offering it", release.version)
            return ""
        return None

    def _version_received(self, release, response):
        problem = _failure(response)
        if problem:
            return self._check_failed(problem)
        try:
            version, min_loader = read_version_info(response.body.decode("utf-8"))
        except UnicodeDecodeError:
            return self._check_failed("the release's VERSION file cannot be read")
        except UpdateError:
            return self._check_failed("the release's VERSION file cannot be read")
        if version != release.version:
            return self._check_failed(f"the release's VERSION file says v{version}, not v{release.version}")
        self._offer(release, min_loader)

    def _offer(self, release, min_loader):
        reinstall = min_loader > self.loader_version
        if reinstall:
            log.info("v%s needs loader %s (this is %s): manual reinstall", release.version, min_loader, self.loader_version)
        self._end_task()
        self._offered = release
        self.offer = Offer(release.version, self.version, release.notes, release.page_url, reinstall)
        log.info("Offering v%s", release.version)
        self.ui.offer(self.offer)

    def _check_failed(self, problem):
        log.warning("Update check failed: %s", problem)
        manual = self._manual
        self._end_task()
        if manual:
            self.ui.message(f"Could not check for updates: {problem}.")

    def _check_done(self, text):
        log.info("Update check: %s", text or "nothing to offer")
        manual = self._manual
        self._end_task()
        if manual and text:
            self.ui.message(text)

    # -- the dialog's buttons --------------------------------------------------------

    def later(self):
        self.offer = self._offered = None

    def skip(self):
        if self.offer is not None:
            log.info("Skipping v%s", self.offer.version)
            self.state["skippedVersion"] = self.offer.version
            self.save_state()
        self.later()

    def update(self):
        """**Update**: download, verify and unpack the offered release."""
        release, offer = self._offered, self.offer
        if release is None or offer is None or offer.reinstall or self._task is not None:
            return
        self.offer = self._offered = None
        if release.zip_url is None or release.sums_url is None:
            missing = release.zip_name if release.zip_url is None else SUMS_ASSET
            return self._update_failed(release, f"the release has no {missing}")
        self._task, self._downloading = "update", release
        log.info("Downloading v%s", release.version)
        self.ui.busy(f"Downloading Shelf+ v{release.version}…")
        self._get(release.sums_url, lambda r: self._sums_received(release, r))

    def _staging_dir(self, release):
        return self.versions_dir / (".download-" + release.version)

    def _sums_received(self, release, response):
        problem = _failure(response)
        if problem:
            return self._update_failed(release, problem)
        try:
            expected = parse_sums(response.body.decode("utf-8", errors="replace"), release.zip_name)
        except UpdateError as exc:
            return self._update_failed(release, str(exc))
        self._get(release.zip_url, lambda r: self._zip_received(release, expected, r))

    def _zip_received(self, release, expected, response):
        problem = _failure(response)
        if problem:
            return self._update_failed(release, problem)
        staging = self._staging_dir(release)
        try:
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True)
            zip_path = staging / release.zip_name
            zip_path.write_bytes(response.body)
            verify_sha256(zip_path, expected)
            install_zip(zip_path, self.versions_dir, release.version, self.loader_version)
        except NeedsReinstall:
            shutil.rmtree(staging, ignore_errors=True)
            self._end_task()
            self._offered = release
            self.offer = Offer(release.version, self.version, release.notes, release.page_url, reinstall=True)
            self.ui.offer(self.offer)
            return
        except UpdateError as exc:
            return self._update_failed(release, str(exc))
        except OSError as exc:
            return self._update_failed(release, f"it could not be saved ({exc})")
        shutil.rmtree(staging, ignore_errors=True)
        try:
            apply_retention(self.versions_dir, read_bad_versions(self.data_dir), self.loader_version, keep=[self.version])
        except OSError:
            log.exception("Removing old versions failed")
        log.info("Installed v%s; active the next time Painter starts", release.version)
        self._end_task()
        self.ui.message(UPDATED_MESSAGE)

    def _update_failed(self, release, problem):
        log.warning("Update to v%s failed: %s", release.version, problem)
        shutil.rmtree(self._staging_dir(release), ignore_errors=True)
        shutil.rmtree(self.versions_dir / (".staging-" + release.version), ignore_errors=True)
        self._end_task()
        self.ui.message(f"Shelf+ could not be updated to v{release.version}: {problem}. v{self.version} stays in use.")

    # -- plumbing ----------------------------------------------------------------------

    def _get(self, url, callback, accept=None):
        def done(response):
            self._request = None
            if self._closed:
                return
            try:
                callback(response)
            except Exception:
                log.exception("The updater failed")
                manual = self._manual or self._task == "update"
                self._end_task()
                if manual:
                    self.ui.message("Shelf+ could not check for updates or update. See the log.")

        self._request = self.network.get(url, done, accept=accept)

    def _end_task(self):
        self._task, self._manual, self._downloading = None, False, None
        self.ui.busy(None)

    def close(self):
        """Abort the request in flight; a half-done download leaves no staging folder."""
        self._closed = True
        request, self._request = self._request, None
        if request is not None:
            try:
                request.abort()
            except Exception:
                log.exception("Aborting the update request failed")
        if self._downloading is not None:
            shutil.rmtree(self._staging_dir(self._downloading), ignore_errors=True)
            self._downloading = None
