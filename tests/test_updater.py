"""Self-update (PRD R9): the pure updater against a fake network."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from shelfplus_app.core import updater as up
from shelfplus_app.core.updater import LATEST_URL, Response, Updater

DAY = 24 * 60 * 60
ZIP_URL = "https://github.com/x/releases/download/v0.2.0/ShelfPlus-v0.2.0.zip"
SUMS_URL = "https://github.com/x/releases/download/v0.2.0/SHA256SUMS"
VERSION_URL = "https://github.com/x/releases/download/v0.2.0/VERSION"


class FakeRequest:
    def __init__(self, network, url, on_done, accept):
        self.network, self.url, self.on_done, self.accept = network, url, on_done, accept
        self.aborted = False

    def abort(self):
        self.aborted = True


class FakeNetwork:
    """Holds every request until the test answers it, like a real asynchronous GET."""

    def __init__(self):
        self.requests = []

    def get(self, url, on_done, accept=None):
        request = FakeRequest(self, url, on_done, accept)
        self.requests.append(request)
        return request

    @property
    def pending(self):
        return [r for r in self.requests if not r.aborted and not getattr(r, "answered", False)]

    def answer(self, url, status=200, body=b"", error=None):
        request = next(r for r in self.pending if r.url == url)
        request.answered = True
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        request.on_done(Response(status=status, body=body, error=error))


class FakeUi:
    def __init__(self):
        self.offers, self.messages, self.busy_texts = [], [], []

    def offer(self, offer):
        self.offers.append(offer)

    def message(self, text):
        self.messages.append(text)

    def busy(self, text):
        self.busy_texts.append(text)


def make_zip(version="0.2.0", min_loader=1, extra=None, with_app=True):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("ShelfPlus/__init__.py", "# loader\n")
        z.writestr("ShelfPlus/VERSION", json.dumps({"version": version, "min_loader": min_loader}))
        z.writestr("ShelfPlus/bundled/default_layout.json", "{}")
        if with_app:
            z.writestr("ShelfPlus/bundled/shelfplus_app/__init__.py", f"VERSION = {version!r}\n")
            z.writestr("ShelfPlus/bundled/shelfplus_app/core/updater.py", "# new\n")
        for name, text in (extra or {}).items():
            z.writestr(name, text)
    return data.getvalue()


def sums_for(blob, name="ShelfPlus-v0.2.0.zip"):
    return f"{hashlib.sha256(blob).hexdigest()}  {name}\n"


def release_json(tag="v0.2.0", prerelease=False, assets=("zip", "sums", "version"), body="* New things"):
    urls = {"zip": ("ShelfPlus-v0.2.0.zip", ZIP_URL), "sums": ("SHA256SUMS", SUMS_URL), "version": ("VERSION", VERSION_URL)}
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "draft": False,
        "body": body,
        "html_url": f"https://github.com/x/releases/tag/{tag}",
        "assets": [{"name": urls[a][0], "browser_download_url": urls[a][1]} for a in assets],
    }


def install_version(data_dir, version, min_loader=1):
    folder = Path(data_dir) / "versions" / version
    (folder / "shelfplus_app").mkdir(parents=True)
    (folder / "shelfplus_app" / "__init__.py").write_text("", encoding="utf-8")
    (folder / "VERSION").write_text(json.dumps({"version": version, "min_loader": min_loader}), encoding="utf-8")
    return folder


class Harness:
    def __init__(self, data_dir, version="0.1.0", loader_version=1, now=1_000_000.0, state=None):
        self.data_dir = Path(data_dir)
        install_version(self.data_dir, version)
        self.network = FakeNetwork()
        self.ui = FakeUi()
        self.state = state if state is not None else {"lastCheck": None, "skippedVersion": None}
        self.saves = 0
        self.now = now
        self.updater = Updater(
            self.network, self.data_dir, version, loader_version, self.state, self._save, self.ui, clock=lambda: self.now
        )

    def _save(self):
        self.saves += 1

    def offer_release(self, manual=False, min_loader=1, **release):
        if manual:
            self.updater.check_now()
        else:
            assert self.updater.check_on_start()
        self.network.answer(LATEST_URL, body=release_json(**release))
        self.network.answer(VERSION_URL, body={"version": "0.2.0", "min_loader": min_loader})

    def installed(self):
        return sorted(v for v, _ in up.installed_versions(self.data_dir / "versions"))

    def leftovers(self):
        return sorted(p.name for p in (self.data_dir / "versions").iterdir() if p.name.startswith("."))


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path)


# -- version comparison --------------------------------------------------------


@pytest.mark.parametrize(
    "candidate, current, newer",
    [
        ("0.2.0", "0.1.0", True),
        ("0.10.0", "0.9.9", True),  # numbers, not text
        ("1.0.0", "0.99.99", True),
        ("0.1.0", "0.1.0", False),
        ("0.1.0", "0.2.0", False),
        ("0.2", "0.1.0", False),
        ("v0.2.0", "0.1.0", False),
        (None, "0.1.0", False),
    ],
)
def test_version_comparison(candidate, current, newer):
    assert up.is_newer(candidate, current) is newer


def test_parse_release_reads_version_notes_and_assets():
    release = up.parse_release(release_json())

    assert (release.version, release.tag, release.notes) == ("0.2.0", "v0.2.0", "* New things")
    assert (release.zip_url, release.sums_url, release.version_url) == (ZIP_URL, SUMS_URL, VERSION_URL)


@pytest.mark.parametrize("data", [release_json(prerelease=True), release_json(tag="v0.2.0-rc.1"), {**release_json(), "draft": True}])
def test_prereleases_and_drafts_are_ignored(data):
    assert up.parse_release(data) is None


def test_a_prerelease_from_github_is_not_offered(h):
    h.updater.check_now()
    h.network.answer(LATEST_URL, body=release_json(prerelease=True))

    assert h.ui.offers == []
    assert h.ui.messages == ["Shelf+ v0.1.0 is up to date."]


# -- the 24 h throttle ---------------------------------------------------------


@pytest.mark.parametrize(
    "last, due",
    [(None, True), ("yesterday", True), (1_000_000.0 - DAY, True), (1_000_000.0 - DAY + 1, False), (1_000_000.0, False), (1_000_000.0 + 60, True)],
)
def test_check_due(last, due):
    assert up.check_due(last, 1_000_000.0) is due


def test_start_up_check_runs_once_a_day_and_records_the_time(h):
    assert h.updater.check_on_start()
    assert h.state["lastCheck"] == h.now and h.saves == 1
    assert [r.url for r in h.network.requests] == [LATEST_URL]
    assert h.network.requests[0].accept == "application/vnd.github+json"
    h.network.answer(LATEST_URL, body=release_json(tag="v0.1.0"))

    h.now += DAY - 1
    assert not h.updater.check_on_start()
    assert len(h.network.requests) == 1

    h.now += 1
    assert h.updater.check_on_start()
    assert len(h.network.requests) == 2


def test_manual_check_ignores_the_throttle(h):
    h.state["lastCheck"] = h.now
    h.updater.check_now()

    assert [r.url for r in h.network.requests] == [LATEST_URL]
    assert h.ui.busy_texts == ["Checking for updates…"]


# -- offering ------------------------------------------------------------------


def test_a_newer_version_is_offered_with_its_notes(h):
    h.offer_release()

    [offer] = h.ui.offers
    assert offer.text == "Shelf+ v0.2.0 is available (you have v0.1.0)."
    assert (offer.version, offer.notes, offer.reinstall) == ("0.2.0", "* New things", False)
    assert h.updater.offer is offer


def test_the_same_version_is_up_to_date(h):
    h.updater.check_now()
    h.network.answer(LATEST_URL, body=release_json(tag="v0.1.0"))

    assert h.ui.offers == [] and h.ui.messages == ["Shelf+ v0.1.0 is up to date."]


def test_skip_stores_the_version_and_it_is_not_offered_again(h):
    h.offer_release()
    h.updater.skip()

    assert h.state["skippedVersion"] == "0.2.0"
    assert h.updater.offer is None
    h.now += DAY
    h.updater.check_on_start()
    h.network.answer(LATEST_URL, body=release_json())
    assert len(h.ui.offers) == 1 and h.ui.messages == []
    assert VERSION_URL not in [r.url for r in h.network.pending]


def test_a_newer_version_than_the_skipped_one_is_offered(h):
    h.state["skippedVersion"] = "0.1.5"
    h.offer_release()

    assert [o.version for o in h.ui.offers] == ["0.2.0"]


def test_a_manual_check_still_offers_the_skipped_version(h):
    h.state["skippedVersion"] = "0.2.0"
    h.offer_release(manual=True)

    assert [o.version for o in h.ui.offers] == ["0.2.0"]


def test_later_offers_it_again_at_the_next_check(h):
    h.offer_release()
    h.updater.later()

    assert h.state["skippedVersion"] is None
    h.offer_release(manual=True)
    assert len(h.ui.offers) == 2


def test_a_version_marked_bad_is_never_offered(h):
    (h.data_dir / "loader.json").write_text(json.dumps({"bad_versions": ["0.2.0"]}), encoding="utf-8")
    h.updater.check_now()
    h.network.answer(LATEST_URL, body=release_json())

    assert h.ui.offers == []
    assert h.ui.messages == ["Shelf+ v0.1.0 is up to date."]


def test_an_already_downloaded_version_is_not_offered(h):
    install_version(h.data_dir, "0.2.0")
    h.updater.check_now()
    h.network.answer(LATEST_URL, body=release_json())

    assert h.ui.offers == []
    assert "already downloaded" in h.ui.messages[0]


# -- the min_loader gate -------------------------------------------------------


def test_a_release_needing_a_newer_loader_is_a_manual_reinstall(h):
    h.offer_release(min_loader=2)

    [offer] = h.ui.offers
    assert offer.reinstall
    assert "needs a manual reinstall" in offer.text
    assert offer.page_url == "https://github.com/x/releases/tag/v0.2.0"
    h.updater.update()  # nothing to download
    assert [r.url for r in h.network.requests] == [LATEST_URL, VERSION_URL]


def test_a_zip_needing_a_newer_loader_is_not_installed(h):
    h.offer_release()  # the VERSION asset said 1, the zip says 2
    blob = make_zip(min_loader=2)
    h.updater.update()
    h.network.answer(SUMS_URL, body=sums_for(blob))
    h.network.answer(ZIP_URL, body=blob)

    assert h.installed() == ["0.1.0"] and h.leftovers() == []
    assert h.ui.offers[-1].reinstall


def test_without_a_version_asset_min_loader_is_one(h):
    h.updater.check_now()
    h.network.answer(LATEST_URL, body=release_json(assets=("zip", "sums")))

    assert [o.reinstall for o in h.ui.offers] == [False]


# -- updating ------------------------------------------------------------------


def test_update_downloads_verifies_and_unpacks_into_versions(h):
    h.offer_release()
    blob = make_zip()
    h.updater.update()
    assert h.ui.busy_texts[-1] == "Downloading Shelf+ v0.2.0…"
    h.network.answer(SUMS_URL, body=sums_for(blob))
    h.network.answer(ZIP_URL, body=blob)

    folder = h.data_dir / "versions" / "0.2.0"
    assert (folder / "shelfplus_app" / "__init__.py").read_text(encoding="utf-8") == "VERSION = '0.2.0'\n"
    assert (folder / "default_layout.json").is_file()
    assert json.loads((folder / "VERSION").read_text(encoding="utf-8"))["version"] == "0.2.0"
    assert not (folder / "__init__.py").exists()  # the loader is not part of a version
    assert h.installed() == ["0.1.0", "0.2.0"] and h.leftovers() == []
    assert h.ui.messages == ["Update downloaded; it will be active the next time Painter starts."]
    assert h.ui.busy_texts[-1] is None


def test_checksum_mismatch_installs_nothing_and_cleans_up(h):
    h.offer_release()
    h.updater.update()
    h.network.answer(SUMS_URL, body=sums_for(b"something else"))
    h.network.answer(ZIP_URL, body=make_zip())

    assert h.installed() == ["0.1.0"] and h.leftovers() == []
    assert h.ui.messages == [
        "Shelf+ could not be updated to v0.2.0: the download does not match its SHA-256 checksum. v0.1.0 stays in use."
    ]


def test_sums_without_the_zip_fail(h):
    h.offer_release()
    h.updater.update()
    h.network.answer(SUMS_URL, body="0" * 64 + "  other.zip\n")

    assert "SHA256SUMS has no checksum for ShelfPlus-v0.2.0.zip" in h.ui.messages[0]
    assert ZIP_URL not in [r.url for r in h.network.requests]


@pytest.mark.parametrize("answer", [{"status": None, "error": "Host not found"}, {"status": 404}])
def test_a_failed_download_shows_a_message(h, answer):
    h.offer_release()
    h.updater.update()
    h.network.answer(SUMS_URL, body=sums_for(b"x"))
    h.network.answer(ZIP_URL, **answer)

    assert h.ui.messages[0].startswith("Shelf+ could not be updated to v0.2.0:")
    assert h.installed() == ["0.1.0"] and h.leftovers() == []


@pytest.mark.parametrize(
    "blob",
    [
        b"not a zip",
        make_zip(version="0.3.0"),
        make_zip(with_app=False),
        make_zip(extra={"ShelfPlus/bundled/../../evil.py": "x"}),
    ],
)
def test_a_bad_zip_is_not_installed_and_staging_is_removed(h, blob):
    h.offer_release()
    h.updater.update()
    h.network.answer(SUMS_URL, body=sums_for(blob))
    h.network.answer(ZIP_URL, body=blob)

    assert h.installed() == ["0.1.0"] and h.leftovers() == []
    assert not (h.data_dir / "evil.py").exists()
    assert h.ui.messages[0].startswith("Shelf+ could not be updated to v0.2.0:")


def test_a_release_without_its_zip_fails_without_downloading(h):
    h.offer_release(assets=("sums", "version"))
    h.updater.update()

    assert "the release has no ShelfPlus-v0.2.0.zip" in h.ui.messages[0]
    assert [r.url for r in h.network.requests] == [LATEST_URL, VERSION_URL]


def test_closing_mid_download_aborts_and_cleans_up(h):
    h.offer_release()
    h.updater.update()
    h.network.answer(SUMS_URL, body=sums_for(b"x"))
    staging = h.data_dir / "versions" / ".download-0.2.0"
    staging.mkdir()
    request = h.network.pending[0]

    h.updater.close()

    assert request.aborted
    assert h.leftovers() == []


def test_update_while_downloading_is_refused_by_check(h):
    h.offer_release()
    h.updater.update()
    h.updater.check_now()

    assert h.ui.messages == ["An update is already downloading."]


# -- retention -----------------------------------------------------------------


def test_update_keeps_only_the_two_newest_versions(tmp_path):
    h = Harness(tmp_path, version="0.1.5")
    install_version(tmp_path, "0.1.0")
    install_version(tmp_path, "0.0.9")
    h.offer_release()
    blob = make_zip()
    h.updater.update()
    h.network.answer(SUMS_URL, body=sums_for(blob))
    h.network.answer(ZIP_URL, body=blob)

    assert h.installed() == ["0.1.5", "0.2.0"]


def test_retention_keeps_the_running_version_and_ones_needing_a_newer_loader(tmp_path):
    versions = tmp_path / "versions"
    for v in ("0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0"):
        install_version(tmp_path, v)
    install_version(tmp_path, "0.9.0", min_loader=5)

    removed = up.apply_retention(versions, bad_versions=["0.5.0"], loader_version=1, keep=["0.1.0"])

    assert sorted(removed) == ["0.2.0", "0.5.0"]
    assert sorted(v for v, _ in up.installed_versions(versions)) == ["0.1.0", "0.3.0", "0.4.0", "0.9.0"]


# -- errors on checking --------------------------------------------------------


@pytest.mark.parametrize(
    "answer, reason",
    [
        ({"status": None, "error": "Host api.github.com not found"}, "Host api.github.com not found"),
        ({"status": 403, "error": "Forbidden"}, "GitHub's rate limit was reached"),
        ({"status": 500}, "HTTP 500"),
        ({"status": 200, "body": "<html>"}, "cannot be read"),
    ],
)
def test_a_manual_check_shows_every_error(h, answer, reason):
    h.updater.check_now()
    h.network.answer(LATEST_URL, **answer)

    [message] = h.ui.messages
    assert message.startswith("Could not check for updates:") and reason in message


def test_the_start_up_check_is_silent_on_errors(h):
    h.updater.check_on_start()
    h.network.answer(LATEST_URL, status=None, error="Host not found")

    assert h.ui.messages == [] and h.ui.offers == []


def test_a_manual_check_during_the_start_up_check_shows_its_result(h):
    h.updater.check_on_start()
    h.updater.check_now()
    assert len(h.network.requests) == 1
    h.network.answer(LATEST_URL, status=None, error="Host not found")

    assert h.ui.messages == ["Could not check for updates: Host not found."]


def test_answers_after_close_are_ignored(h):
    h.updater.check_now()
    h.updater.close()
    h.network.requests[0].on_done(Response(status=200, body=json.dumps(release_json()).encode()))

    assert h.ui.offers == [] and h.ui.messages == []


# -- small parsers -------------------------------------------------------------


def test_parse_sums_accepts_binary_marker_and_case():
    digest = "A" * 64
    assert up.parse_sums(f"{digest} *ShelfPlus-v0.2.0.zip\n", "ShelfPlus-v0.2.0.zip") == "a" * 64


def test_bad_versions_come_from_loader_json(tmp_path):
    assert up.read_bad_versions(tmp_path) == []
    (tmp_path / "loader.json").write_text(json.dumps({"bad_versions": ["0.3.0", 7]}), encoding="utf-8")
    assert up.read_bad_versions(tmp_path) == ["0.3.0"]
