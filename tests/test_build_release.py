"""The release build (PRD R11): zip layout, VERSION, SHA256SUMS, tag check."""

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("build_release", ROOT / "tools" / "build_release.py")
build_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_release)

VERSION = json.loads((ROOT / "src" / "ShelfPlus" / "VERSION").read_text(encoding="utf-8"))["version"]


def test_builds_the_zip_and_checksums(tmp_path):
    (ROOT / "src" / "ShelfPlus" / "bundled" / "shelfplus_app" / "__pycache__").mkdir(exist_ok=True)

    zip_path = build_release.build(f"v{VERSION}", tmp_path)

    assert zip_path.name == f"ShelfPlus-v{VERSION}.zip"
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        assert "ShelfPlus/__init__.py" in names
        assert "ShelfPlus/_versions.py" in names
        assert "ShelfPlus/bundled/default_layout.json" in names
        assert "ShelfPlus/bundled/shelfplus_app/__init__.py" in names
        assert "ShelfPlus/bundled/shelfplus_app/core/storage.py" in names
        assert all(n.startswith("ShelfPlus/") for n in names)
        assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
        version = json.loads(z.read("ShelfPlus/VERSION"))
        assert version == {"version": VERSION, "min_loader": version["min_loader"]}
        assert isinstance(version["min_loader"], int)

    sums = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8")
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert sums == f"{digest}  {zip_path.name}\n"


def test_build_is_reproducible(tmp_path):
    a = build_release.build(f"v{VERSION}", tmp_path / "a")
    b = build_release.build(f"v{VERSION}", tmp_path / "b")

    assert a.read_bytes() == b.read_bytes()


def test_a_prerelease_tag_keeps_the_plain_version_inside(tmp_path):
    zip_path = build_release.build(f"v{VERSION}-rc.1", tmp_path)

    assert zip_path.name == f"ShelfPlus-v{VERSION}-rc.1.zip"
    with zipfile.ZipFile(zip_path) as z:
        assert json.loads(z.read("ShelfPlus/VERSION"))["version"] == VERSION


@pytest.mark.parametrize("tag", ["v9.9.9", "0.1.0", "v0.1", "release"])
def test_rejects_a_tag_that_does_not_match_version(tmp_path, tag):
    with pytest.raises(SystemExit):
        build_release.build(tag, tmp_path)
