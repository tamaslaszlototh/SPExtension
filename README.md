# Shelf+

A Python plugin for Adobe Substance 3D Painter (11.1 and 12.2, Windows) that adds one
dockable **Panel** of the user's own Buttons, arranged in Groups. Terms are defined in
[GLOSSARY.md](GLOSSARY.md); the v1 spec is the PRD in issue #23.

## Install

1. Download `ShelfPlus-vX.Y.Z.zip` from the GitHub Releases page.
2. Copy the `ShelfPlus` folder from the zip into
   `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`.
3. In Painter, enable **ShelfPlus** in the **Python** menu.

No admin rights are needed. Data lives in `%APPDATA%\ShelfPlus\`.

## Repository layout

```
src/ShelfPlus/              the plugin folder, exactly as it ships in the zip
  __init__.py               loader entry point (start_plugin / close_plugin)
  _versions.py              version install, selection, bad-version rollback, retention
  VERSION                   {"version": ..., "min_loader": ...}
  bundled/
    default_layout.json     copied to %APPDATA%\ShelfPlus\layout.json on first start
    shelfplus_app/          the application, copied to %APPDATA%\ShelfPlus\versions\<v>\
      core/                 pure Python: Layout schema, storage, panel.json, diagnostics
      adapter/              painter.py (the only substance_painter user) and fake.py (tests)
      ui/                   Qt widgets
      app.py                wires core, adapter and view together
tools/build_release.py      builds the release zip and SHA256SUMS
tests/                      pytest, outside Painter
```

The loader rarely changes. It installs `bundled/` into `versions/<v>/`, starts the
highest version not listed in `%APPDATA%\ShelfPlus\loader.json` as bad, and keeps the
two newest good versions. Bump `LOADER_VERSION` in `_versions.py` and `min_loader` in
`VERSION` together when the application needs a newer loader.

## Development

```
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```

Runtime code uses only the standard library, PySide6 and `substance_painter`, and must
stay Python 3.11 compatible. CI runs the tests on 3.11 and 3.13.

## Releasing

1. Set `version` in `src/ShelfPlus/VERSION` and commit.
2. Push an annotated tag: `git tag -a v0.1.0 -m "Release notes"` then `git push origin v0.1.0`.

The Release workflow tests, builds `ShelfPlus-v0.1.0.zip` and `SHA256SUMS`, and
publishes a GitHub Release with the tag message as its notes. A tag with a suffix
(`v0.1.0-rc.1`) must still match `VERSION`; it is published as a pre-release, which
the updater ignores, so it is safe for testing the pipeline.
