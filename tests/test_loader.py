"""Loader: install from bundled/, version selection, bad-version rollback, retention, cleanup.

The loader is exercised with real directories and the real import machinery. The
application package is called ``fakeapp`` here so the tests never collide with the
real ``shelfplus_app`` package.
"""

import json
import sys
import textwrap

import pytest

from ShelfPlus import _versions
from ShelfPlus._versions import VersionManager

APP = "fakeapp"

GOOD_APP = """
    def start_plugin(env):
        env["calls"].append(("start", env["version"]))

    def close_plugin():
        import builtins
        builtins._fakeapp_closed.append(__name__)
"""

FAILS_ON_IMPORT = """
    raise ImportError("broken build")
"""

FAILS_ON_START = """
    def start_plugin(env):
        env["calls"].append(("start", env["version"]))
        raise RuntimeError("start failed")

    def close_plugin():
        import builtins
        builtins._fakeapp_closed.append(__name__)
"""


@pytest.fixture(autouse=True)
def _isolate_modules(monkeypatch):
    import builtins

    monkeypatch.setattr(builtins, "_fakeapp_closed", [], raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield
    for name in [n for n in sys.modules if n == APP or n.startswith(APP + ".")]:
        del sys.modules[name]


def write_app(version_dir, source, version=None, min_loader=1, submodule=False):
    pkg = version_dir / APP
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(source), encoding="utf-8")
    if submodule:
        (pkg / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    if version is not None:
        (version_dir / "VERSION").write_text(
            json.dumps({"version": version, "min_loader": min_loader}), encoding="utf-8"
        )


@pytest.fixture
def dirs(tmp_path):
    plugin_dir = tmp_path / "plugins" / "ShelfPlus"
    plugin_dir.mkdir(parents=True)
    data_dir = tmp_path / "appdata" / "ShelfPlus"
    return plugin_dir, data_dir


def make_bundle(plugin_dir, version, source=GOOD_APP, min_loader=1):
    (plugin_dir / "VERSION").write_text(
        json.dumps({"version": version, "min_loader": min_loader}), encoding="utf-8"
    )
    write_app(plugin_dir / "bundled", source)
    (plugin_dir / "bundled" / "default_layout.json").write_text("{}", encoding="utf-8")


def install(data_dir, version, source=GOOD_APP, **kw):
    write_app(data_dir / "versions" / version, source, version=version, **kw)


def manager(plugin_dir, data_dir):
    return VersionManager(plugin_dir, data_dir, app_package=APP)


def start(mgr):
    calls = []
    result = mgr.start({"calls": calls})
    return result, calls


def bad_versions(data_dir):
    path = data_dir / "loader.json"
    return json.loads(path.read_text(encoding="utf-8"))["bad_versions"] if path.exists() else []


def installed(data_dir):
    return sorted(p.name for p in (data_dir / "versions").iterdir())


class TestParseVersion:
    def test_parses_semver(self):
        assert _versions.parse_version("1.10.3") == (1, 10, 3)

    @pytest.mark.parametrize("text", ["1.2", "v1.2.3", "1.2.x", "", "1.2.3-rc1", ".staging-1.2.3"])
    def test_rejects_anything_else(self, text):
        assert _versions.parse_version(text) is None


class TestInstallFromBundled:
    def test_first_start_copies_bundled_into_versions(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")

        result, calls = start(manager(plugin_dir, data_dir))

        version_dir = data_dir / "versions" / "0.1.0"
        assert (version_dir / APP / "__init__.py").is_file()
        assert (version_dir / "default_layout.json").is_file()
        assert json.loads((version_dir / "VERSION").read_text())["version"] == "0.1.0"
        assert result.loaded == "0.1.0"
        assert calls == [("start", "0.1.0")]

    def test_does_not_overwrite_an_installed_version(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0", source=FAILS_ON_IMPORT)
        install(data_dir, "0.1.0")

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"
        assert result.failed == []

    def test_leaves_no_staging_folder_behind(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")

        start(manager(plugin_dir, data_dir))

        assert installed(data_dir) == ["0.1.0"]

    def test_does_not_reinstall_a_bad_version(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.2.0")
        install(data_dir, "0.1.0")
        data_dir.joinpath("loader.json").write_text(json.dumps({"bad_versions": ["0.2.0"]}))

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"
        assert "0.2.0" not in installed(data_dir)


    def test_skips_a_bundled_version_that_retention_would_remove(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0")
        install(data_dir, "0.3.0")

        start(manager(plugin_dir, data_dir))

        assert installed(data_dir) == ["0.2.0", "0.3.0"]

    def test_installs_a_superseded_bundled_version_when_nothing_newer_starts(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0", source=FAILS_ON_IMPORT)
        install(data_dir, "0.3.0", source=FAILS_ON_START)

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"
        assert result.message == "Shelf+ v0.3.0 failed to start; reverted to v0.1.0."


class TestVersionSelection:
    def test_loads_the_highest_installed_version(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0")
        install(data_dir, "0.10.0")  # numeric, not string, comparison

        result, calls = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.10.0"
        assert calls == [("start", "0.10.0")]

    def test_skips_versions_marked_bad(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0")
        data_dir.joinpath("loader.json").write_text(json.dumps({"bad_versions": ["0.2.0"]}))

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"

    def test_skips_versions_needing_a_newer_loader_without_marking_them_bad(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0", min_loader=99)

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"
        assert "0.2.0" not in bad_versions(data_dir)

    def test_ignores_folders_that_are_not_versions(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        (data_dir / "versions" / "notes").mkdir(parents=True)
        (data_dir / "versions" / "9.9.9").mkdir()  # empty: no application package

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"

    def test_passes_version_details_to_the_application(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        seen = {}
        install(
            data_dir,
            "0.2.0",
            source="""
                def start_plugin(env):
                    env["seen"].update(env)
                def close_plugin():
                    pass
            """,
        )

        manager(plugin_dir, data_dir).start({"seen": seen})

        assert seen["version"] == "0.2.0"
        assert seen["version_dir"] == str(data_dir / "versions" / "0.2.0")
        assert seen["data_dir"] == str(data_dir)
        assert seen["loader_version"] == _versions.LOADER_VERSION


class TestBadVersionRollback:
    def test_import_error_marks_bad_and_rolls_back(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0", source=FAILS_ON_IMPORT)

        result, calls = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"
        assert [f.version for f in result.failed] == ["0.2.0"]
        assert "broken build" in result.failed[0].traceback
        assert bad_versions(data_dir) == ["0.2.0"]
        assert result.message == "Shelf+ v0.2.0 failed to start; reverted to v0.1.0."
        assert calls == [("start", "0.1.0")]

    def test_start_plugin_error_marks_bad_cleans_up_and_rolls_back(self, dirs):
        import builtins

        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0", source=FAILS_ON_START)

        result, calls = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"
        assert bad_versions(data_dir) == ["0.2.0"]
        assert calls == [("start", "0.2.0"), ("start", "0.1.0")]
        assert builtins._fakeapp_closed == [APP]  # the failed start got a chance to clean up

    def test_rolls_back_over_several_bad_versions(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.3.0", source=FAILS_ON_IMPORT)
        install(data_dir, "0.2.0", source=FAILS_ON_START)

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"
        assert sorted(bad_versions(data_dir)) == ["0.2.0", "0.3.0"]
        assert result.message == "Shelf+ v0.3.0 failed to start; reverted to v0.1.0."

    def test_reports_when_nothing_can_start(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0", source=FAILS_ON_IMPORT)

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded is None
        assert result.message == "Shelf+ v0.1.0 failed to start, and no earlier version is available."

    def test_failed_import_leaves_no_modules_or_path_behind(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0", source=FAILS_ON_IMPORT)

        start(manager(plugin_dir, data_dir))

        assert APP not in sys.modules
        assert str(data_dir / "versions" / "0.1.0") not in sys.path

    def test_a_broken_loader_json_is_treated_as_empty(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        data_dir.mkdir(parents=True)
        data_dir.joinpath("loader.json").write_text("{not json")

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.1.0"


class TestRetention:
    def test_never_removes_the_running_version_for_versions_needing_a_newer_loader(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0")
        install(data_dir, "0.3.0", min_loader=99)
        install(data_dir, "0.4.0", min_loader=99)

        result, _ = start(manager(plugin_dir, data_dir))

        assert result.loaded == "0.2.0"
        assert installed(data_dir) == ["0.1.0", "0.2.0", "0.3.0", "0.4.0"]

    def test_keeps_the_two_newest_good_versions(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0")
        install(data_dir, "0.3.0")
        install(data_dir, "0.4.0")

        start(manager(plugin_dir, data_dir))

        assert installed(data_dir) == ["0.3.0", "0.4.0"]

    def test_bad_versions_do_not_count_and_are_removed(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0")
        install(data_dir, "0.3.0", source=FAILS_ON_IMPORT)

        start(manager(plugin_dir, data_dir))

        assert installed(data_dir) == ["0.1.0", "0.2.0"]
        assert bad_versions(data_dir) == ["0.3.0"]  # still remembered after removal

    def test_nothing_is_removed_when_nothing_started(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0", source=FAILS_ON_IMPORT)
        install(data_dir, "0.2.0", source=FAILS_ON_IMPORT)

        start(manager(plugin_dir, data_dir))

        assert installed(data_dir) == ["0.1.0", "0.2.0"]


class TestStop:
    def test_stop_closes_the_application_and_clears_its_modules(self, dirs):
        import builtins

        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(data_dir, "0.2.0", source=GOOD_APP + "\n    from . import helper\n", submodule=True)
        mgr = manager(plugin_dir, data_dir)
        start(mgr)
        assert APP + ".helper" in sys.modules

        mgr.stop()

        assert builtins._fakeapp_closed == [APP]
        assert not [n for n in sys.modules if n == APP or n.startswith(APP + ".")]
        assert str(data_dir / "versions" / "0.2.0") not in sys.path

    def test_restart_after_stop_imports_fresh_code(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        mgr = manager(plugin_dir, data_dir)
        start(mgr)
        first = sys.modules[APP]
        mgr.stop()

        start(mgr)

        assert sys.modules[APP] is not first

    def test_stop_without_start_is_harmless(self, dirs):
        plugin_dir, data_dir = dirs
        manager(plugin_dir, data_dir).stop()

    def test_stop_survives_a_failing_close_plugin(self, dirs):
        plugin_dir, data_dir = dirs
        make_bundle(plugin_dir, "0.1.0")
        install(
            data_dir,
            "0.2.0",
            source="""
                def start_plugin(env):
                    pass
                def close_plugin():
                    raise RuntimeError("close failed")
            """,
        )
        mgr = manager(plugin_dir, data_dir)
        start(mgr)

        mgr.stop()

        assert APP not in sys.modules
