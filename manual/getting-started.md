# Getting started

## Requirements

- **Adobe Substance 3D Painter** with Python plugins enabled.
- Tested on **Windows** with **Painter 11.1** and **Painter 12.2**.
- No admin rights are needed.
- An internet connection is needed only for update checks.

## Install

1. Close Painter.
2. Download `ShelfPlus-vX.Y.Z.zip` (the newest version) from the
   [Releases page](https://github.com/tamaslaszlototh/ShelfPlus/releases).
3. Open this folder in File Explorer:
   `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`
4. If there is a `ShelfPlus` folder there already, delete it.
5. Copy the `ShelfPlus` folder from the zip into the `plugins` folder.
6. Start Painter. In the **Python** menu, make sure **ShelfPlus** is enabled.

You need to install by hand only once. After that, Shelf+
[updates itself](updates.md).

!!! tip "Where your data lives"
    Your Buttons, Groups and settings are stored in `%APPDATA%\ShelfPlus\`. Paste that
    path into the File Explorer address bar to open it. Deleting the plugin folder does
    not delete your Buttons.

## Open the Panel

The Panel opens when Painter starts. If you closed it, open it again from
**Window → Views → Shelf+**.

Like any Painter window, you can dock it at a side of Painter, put it in a tab, or let it
float. The Panel [adapts its layout](panel.md#tall-and-wide-panels) to its shape.

To check which version you have, click **☰** in the Panel's top right corner. The first
line shows it, for example **Shelf+ v1.0.0**.

## Your first Button

A Brush button is the quickest one to try.

1. Open a project.
2. Open the Assets window (**Window → Views → Assets**) and find a brush, for example
   *Basic Hard*.
3. Drag the brush onto a Group on the Panel. Drop it between two tiles, or on the Group's
   name.
4. A new tile with the brush's picture appears.
5. Pick a different brush by hand, then click the new tile. *Basic Hard* is the active
   brush again.

## Next steps

- Arrange your Buttons: [The Panel](panel.md)
- Add a menu command: [Menu buttons](menu-buttons.md)
- Do several things with one click: [Workflow buttons](workflow-buttons.md)
