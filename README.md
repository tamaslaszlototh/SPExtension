# Shelf+

A Python plugin for Adobe Substance 3D Painter that adds one
dockable **Panel** of the user's own Buttons, arranged in Groups.

📖 **[Read the User Manual](https://tamaslaszlototh.github.io/ShelfPlus/)**

## Features

- **Brush buttons**: drag a brush or tool preset from the Assets window onto the Panel;
  one click makes it the active brush.
- **Menu buttons**: one click runs a Painter menu command, such as **File → Save**.
- **Workflow buttons**: one click carries out several Steps, for example
  "Fill layer + black mask + Dirt generator + 50% opacity". One **Ctrl+Z** undoes it all.
- **Workflow editor**: build Workflows from layer, mask, effect and setting Steps.
- **Recording**: do the Steps in Painter and let the Panel record them as a Workflow.
- **Self-update** from GitHub Releases, and **Copy diagnostics** for bug reports.

The [User Manual](https://tamaslaszlototh.github.io/ShelfPlus/) describes every feature.

## Install

1. Download `ShelfPlus-vX.Y.Z.zip` from the GitHub Releases page.
2. Copy the `ShelfPlus` folder from the zip into
   `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`.
3. In Painter, enable **ShelfPlus** in the **Python** menu.

No admin rights are needed. Data lives in `%APPDATA%\ShelfPlus\`.

After that, Shelf+ updates itself: on start and with
**☰ → Check for updates** it offers a newer release. An update is
downloaded and becomes active the next time Painter
starts. Only a release that needs a newer loader must be installed by hand again.

## The User Manual

The manual's sources are in [`manual/`](manual/), built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To preview it locally:

```sh
python -m pip install -r requirements-docs.txt
mkdocs serve
```

The [User manual workflow](.github/workflows/pages.yml) publishes it to GitHub Pages
on every `v*` tag, and can be run by hand from the Actions tab.
