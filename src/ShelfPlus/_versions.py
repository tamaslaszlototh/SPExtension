"""Version management for the Shelf+ loader (PRD R1).

Pure Python: no Qt, no ``substance_painter``. The loader keeps the installed
application versions in ``<data_dir>/versions/<x.y.z>/`` and loads the highest one
that is not marked bad. Bad versions are remembered in ``<data_dir>/loader.json``
so they are never loaded (or offered by the updater) again, even after their
folder has been removed.

This module changes rarely. Keep it small, and keep its contract with the
application stable: ``start_plugin(env: dict)`` and ``close_plugin()``.
"""

import importlib
import json
import logging
import os
import re
import shutil
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

LOADER_VERSION = 1
APP_PACKAGE = "shelfplus_app"
KEEP_GOOD_VERSIONS = 2

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

log = logging.getLogger("ShelfPlus.loader")


def parse_version(text):
    """``"1.2.3"`` -> ``(1, 2, 3)``; anything else -> ``None``."""
    match = _VERSION_RE.match(text or "")
    return tuple(int(part) for part in match.groups()) if match else None


def read_version_file(path):
    """Read a ``VERSION`` file. Returns ``(version, min_loader)`` or ``None``."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        version = data["version"]
        min_loader = int(data.get("min_loader", 1))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    if parse_version(version) is None:
        return None
    return version, min_loader


def purge_modules(package):
    """Remove ``package`` and all of its submodules from ``sys.modules``."""
    for name in [n for n in sys.modules if n == package or n.startswith(package + ".")]:
        del sys.modules[name]


@dataclass
class Failure:
    version: str
    traceback: str


@dataclass
class StartResult:
    loaded: str = None
    failed: list = field(default_factory=list)
    message: str = None


class VersionManager:
    def __init__(self, plugin_dir, data_dir, app_package=APP_PACKAGE, loader_version=LOADER_VERSION):
        self.plugin_dir = Path(plugin_dir)
        self.data_dir = Path(data_dir)
        self.versions_dir = self.data_dir / "versions"
        self.state_path = self.data_dir / "loader.json"
        self.app_package = app_package
        self.loader_version = loader_version
        self._module = None
        self._path_entry = None

    # -- state ---------------------------------------------------------------

    def bad_versions(self):
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return [v for v in data.get("bad_versions", []) if isinstance(v, str)]
        except (OSError, ValueError, AttributeError):
            return []

    def _mark_bad(self, version):
        bad = self.bad_versions()
        if version not in bad:
            bad.append(version)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_name(self.state_path.name + ".tmp")
        tmp.write_text(json.dumps({"bad_versions": bad}, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)

    # -- installed versions --------------------------------------------------

    def installed_versions(self):
        """Installed versions, newest first, with their ``min_loader``."""
        found = []
        try:
            entries = list(self.versions_dir.iterdir())
        except OSError:
            return []
        for entry in entries:
            if parse_version(entry.name) is None:
                continue
            if not (entry / self.app_package / "__init__.py").is_file():
                continue
            info = read_version_file(entry / "VERSION")
            min_loader = info[1] if info and info[0] == entry.name else 1
            found.append((entry.name, min_loader))
        found.sort(key=lambda item: parse_version(item[0]), reverse=True)
        return found

    def _good_versions(self):
        """Installed versions this loader can run and that are not bad, newest first."""
        bad = set(self.bad_versions())
        return [
            v for v, min_loader in self.installed_versions()
            if v not in bad and min_loader <= self.loader_version
        ]

    def install_bundled(self, even_if_superseded=False):
        """Copy ``bundled/`` into ``versions/<v>/`` unless already there.

        A bundled version that retention would delete straight away (two newer
        versions are installed) is skipped, unless ``even_if_superseded``.
        Returns True if a new version folder was created.
        """
        info = read_version_file(self.plugin_dir / "VERSION")
        if info is None or not (self.plugin_dir / "bundled").is_dir():
            log.warning("No usable bundled version in %s", self.plugin_dir)
            return False
        version, _ = info
        target = self.versions_dir / version
        if target.exists():
            return False
        if version in self.bad_versions():
            log.info("Bundled v%s is marked bad; not installing it", version)
            return False
        newer = [v for v in self._good_versions() if parse_version(v) > parse_version(version)]
        if len(newer) >= KEEP_GOOD_VERSIONS and not even_if_superseded:
            log.info("Bundled v%s is older than the installed versions; not installing it", version)
            return False
        staging = self.versions_dir / (".staging-" + version)
        shutil.rmtree(staging, ignore_errors=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            self.plugin_dir / "bundled", staging, ignore=shutil.ignore_patterns("__pycache__")
        )
        shutil.copy2(self.plugin_dir / "VERSION", staging / "VERSION")
        os.replace(staging, target)
        log.info("Installed bundled v%s", version)
        return True

    # -- start / stop --------------------------------------------------------

    def start(self, env):
        """Install, then load the highest good version, rolling back over bad ones."""
        result = StartResult()
        self._try_install(even_if_superseded=False)
        self._load_first_good(env, result)
        if result.loaded is None and self._try_install(even_if_superseded=True):
            self._load_first_good(env, result)

        if result.failed:
            first = result.failed[0].version
            if result.loaded:
                result.message = f"Shelf+ v{first} failed to start; reverted to v{result.loaded}."
            else:
                result.message = f"Shelf+ v{first} failed to start, and no earlier version is available."
        elif result.loaded is None:
            result.message = "Shelf+ could not find an installed version to start."
        if result.loaded:
            if len(self._good_versions()) < KEEP_GOOD_VERSIONS:
                self._try_install(even_if_superseded=True)  # keep a fallback around
            self._apply_retention()
        return result

    def _try_install(self, even_if_superseded):
        try:
            return self.install_bundled(even_if_superseded)
        except OSError:
            log.exception("Installing the bundled version failed")
            return False

    def _load_first_good(self, env, result):
        bad = set(self.bad_versions())
        for version, min_loader in self.installed_versions():
            if version in bad:
                continue
            if min_loader > self.loader_version:
                log.info("Skipping v%s: it needs loader %s (this is %s)", version, min_loader, self.loader_version)
                continue
            try:
                self._load(version, env)
            except Exception:
                tb = traceback.format_exc()
                log.error("Shelf+ v%s failed to start:\n%s", version, tb)
                result.failed.append(Failure(version, tb))
                self._mark_bad(version)
                continue
            result.loaded = version
            log.info("Loaded Shelf+ v%s", version)
            return

    def _load(self, version, env):
        version_dir = self.versions_dir / version
        app_env = dict(env)
        app_env.update(
            version=version,
            version_dir=str(version_dir),
            data_dir=str(self.data_dir),
            loader_version=self.loader_version,
        )
        purge_modules(self.app_package)
        sys.path.insert(0, str(version_dir))
        self._path_entry = str(version_dir)
        module = None
        try:
            module = importlib.import_module(self.app_package)
            module.start_plugin(app_env)
        except Exception:
            if module is not None:
                self._close(module)
            self._unload()
            raise
        self._module = module

    def stop(self):
        if self._module is not None:
            self._close(self._module)
            self._module = None
        self._unload()

    def _close(self, module):
        try:
            module.close_plugin()
        except Exception:
            log.exception("close_plugin raised")

    def _unload(self):
        purge_modules(self.app_package)
        if self._path_entry is not None:
            while self._path_entry in sys.path:
                sys.path.remove(self._path_entry)
            self._path_entry = None
        importlib.invalidate_caches()

    # -- retention -----------------------------------------------------------

    def _apply_retention(self):
        # Versions that need a newer loader are left alone: a manual reinstall
        # of the loader makes them usable.
        keep = set(self._good_versions()[:KEEP_GOOD_VERSIONS])
        for version, min_loader in self.installed_versions():
            if version not in keep and min_loader <= self.loader_version:
                log.info("Removing old or bad v%s", version)
                shutil.rmtree(self.versions_dir / version, ignore_errors=True)
