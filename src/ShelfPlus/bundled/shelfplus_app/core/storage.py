"""Layout storage (PRD R3.3-R3.6): ``layout.json`` with backup, recovery and migrations.

Files in the data folder:

- ``layout.json``: the Layout.
- ``layout.bak.json``: the previous ``layout.json``, refreshed before every save.
- ``layout.v<N>.bak.json``: the file as it was before migrating from schema N.
- ``layout.broken-<timestamp>.json``: an unreadable file, set aside and never overwritten.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import jsonio
from .layout import SCHEMA_VERSION, Layout, LayoutError

log = logging.getLogger("ShelfPlus.app.storage")

# schema N -> function turning a schema-N document into a schema-(N+1) document.
MIGRATIONS = {}

READ_ONLY_MESSAGE = "This Layout was saved by a newer Shelf+. Update Shelf+ to edit this Layout."


class ReadOnlyLayoutError(RuntimeError):
    pass


class _Unreadable(Exception):
    pass


@dataclass
class LoadResult:
    layout: Layout
    read_only: bool = False
    messages: list = field(default_factory=list)


@dataclass
class _Loaded:
    layout: Layout
    newer: bool = False
    migrated_from: int = None
    source: Path = None


class LayoutStore:
    def __init__(self, data_dir, default_layout_path, now=datetime.now, migrations=None, schema_version=SCHEMA_VERSION):
        self.data_dir = Path(data_dir)
        self.default_layout_path = Path(default_layout_path)
        self.main = self.data_dir / "layout.json"
        self.backup = self.data_dir / "layout.bak.json"
        self.now = now
        self.migrations = MIGRATIONS if migrations is None else migrations
        self.schema_version = schema_version
        self.read_only = False

    # -- load ----------------------------------------------------------------

    def load(self):
        self.read_only = False
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.main.exists():
            log.info("No layout.json; copying the default Layout in")
            jsonio.copy_atomic(self.default_layout_path, self.main)

        messages = []
        recovered = False
        try:
            loaded = self._load_file(self.main)
        except _Unreadable as error:
            log.warning("layout.json is unreadable: %s", error)
            recovered = True
            kept_main = self._keep_broken(self.main)
            try:
                loaded = self._load_file(self.backup)
                messages.append(f"layout.json could not be read. It was kept as {kept_main}, and the backup was loaded.")
            except _Unreadable as backup_error:
                log.warning("layout.bak.json is unreadable too: %s", backup_error)
                if self.backup.exists():
                    kept_backup = self._keep_broken(self.backup)
                    text = f"layout.json and its backup could not be read. They were kept as {kept_main} and {kept_backup}."
                else:
                    text = f"layout.json could not be read. It was kept as {kept_main}."
                messages.append(text + " The default Layout was loaded.")
                loaded = self._load_default()

        if loaded.newer:
            return self._read_only_result(loaded, messages)

        if loaded.migrated_from is not None:
            old = loaded.migrated_from
            jsonio.copy_atomic(loaded.source, self.data_dir / f"layout.v{old}.bak.json")
            log.info("Migrated the Layout from schema %s to %s", old, self.schema_version)
        if recovered or loaded.migrated_from is not None:
            self.save(loaded.layout)
        return LoadResult(loaded.layout, False, messages)

    def _read_only_result(self, loaded, messages):
        self.read_only = True
        log.warning("Layout schema is newer than %s; read-only", self.schema_version)
        layout = loaded.layout
        own_backup = self.data_dir / f"layout.v{self.schema_version}.bak.json"
        if own_backup.exists():
            try:
                candidate = self._load_file(own_backup)
                if not candidate.newer and candidate.migrated_from is None:
                    layout = candidate.layout
            except _Unreadable:
                pass
        if not self.main.exists():
            jsonio.copy_atomic(loaded.source, self.main)  # keep the user's file, unchanged
        messages.append(READ_ONLY_MESSAGE)
        return LoadResult(layout, True, messages)

    def _load_file(self, path):
        try:
            data = json.loads(Path(path).read_bytes().decode("utf-8-sig"))
        except (OSError, ValueError) as error:
            raise _Unreadable(f"{Path(path).name}: {error}")
        version = data.get("schemaVersion") if isinstance(data, dict) else None
        if not isinstance(version, int) or isinstance(version, bool):
            raise _Unreadable(f"{Path(path).name}: missing schemaVersion")

        if version > self.schema_version:
            try:
                layout = Layout.from_json(data)
            except LayoutError:
                layout = Layout(version)
            return _Loaded(layout, newer=True, source=Path(path))

        migrated_from = None
        if version < self.schema_version:
            migrated_from = version
            data = self._migrate(data, version, path)
        try:
            layout = Layout.from_json(data)
        except LayoutError as error:
            raise _Unreadable(f"{Path(path).name}: {error}")
        return _Loaded(layout, migrated_from=migrated_from, source=Path(path))

    def _migrate(self, data, version, path):
        while version < self.schema_version:
            step = self.migrations.get(version)
            if step is None:
                raise _Unreadable(f"{Path(path).name}: no migration from schema {version}")
            data = step(data)
            version += 1
            data["schemaVersion"] = version
        return data

    def _load_default(self):
        try:
            return self._load_file(self.default_layout_path)
        except _Unreadable:
            log.exception("The bundled default Layout is unreadable")
            return _Loaded(Layout(self.schema_version))

    def _keep_broken(self, path):
        stamp = self.now().strftime("%Y%m%d-%H%M%S")
        target = self.data_dir / f"layout.broken-{stamp}.json"
        counter = 2
        while target.exists():
            target = self.data_dir / f"layout.broken-{stamp}-{counter}.json"
            counter += 1
        os.replace(path, target)
        log.warning("Kept unreadable %s as %s", Path(path).name, target.name)
        return target.name

    # -- save ----------------------------------------------------------------

    def save(self, layout):
        if self.read_only:
            raise ReadOnlyLayoutError(READ_ONLY_MESSAGE)
        if self.main.exists():
            jsonio.copy_atomic(self.main, self.backup)
        jsonio.write_json_atomic(self.main, layout.to_json())
