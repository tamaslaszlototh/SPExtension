"""Build the release zip and SHA256SUMS for a tag.

    python tools/build_release.py v0.1.0 [--out dist]

The zip holds ``ShelfPlus/`` exactly as it goes into Painter's plugins folder: the
loader, ``VERSION`` (version and ``min_loader``) and ``bundled/``. ``VERSION`` is also
published as its own asset, so the updater knows ``min_loader`` before it downloads
anything. The tag must match
the version in ``src/ShelfPlus/VERSION``; a suffix (``v0.1.0-rc.1``) marks a
pre-release and does not change the version inside the zip.
"""

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "src" / "ShelfPlus"
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)(-[0-9A-Za-z.]+)?$")
FIXED_TIME = (2020, 1, 1, 0, 0, 0)  # reproducible zips


def _files():
    for path in sorted(PLUGIN.rglob("*")):
        rel = path.relative_to(PLUGIN)
        if path.is_dir() or "__pycache__" in rel.parts or path.suffix in (".pyc", ".pyo"):
            continue
        yield path, "ShelfPlus/" + rel.as_posix()


def build(tag, out_dir):
    match = TAG_RE.match(tag)
    if not match:
        raise SystemExit(f"Tag {tag!r} is not vX.Y.Z or vX.Y.Z-suffix")
    version_info = json.loads((PLUGIN / "VERSION").read_text(encoding="utf-8"))
    if version_info.get("version") != match.group(1):
        raise SystemExit(f"Tag {tag} does not match src/ShelfPlus/VERSION ({version_info.get('version')})")
    if not isinstance(version_info.get("min_loader"), int):
        raise SystemExit("src/ShelfPlus/VERSION needs an integer min_loader")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"ShelfPlus-{tag}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path, name in _files():
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (out_dir / "SHA256SUMS").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    (out_dir / "VERSION").write_bytes((PLUGIN / "VERSION").read_bytes())  # read by the updater
    return zip_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag")
    parser.add_argument("--out", default=str(ROOT / "dist"))
    args = parser.parse_args(argv)
    zip_path = build(args.tag, args.out)
    print(zip_path)


if __name__ == "__main__":
    sys.exit(main())
