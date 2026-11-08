# Shelf+

A Python plugin for Adobe Substance 3D Painter that adds one
dockable **Panel** of the user's own Buttons, arranged in Groups.

## Features

### The Panel

- One Panel that can be docked or float. Open it from **Window → Views → Shelf+**.
- Buttons are icon tiles, arranged in named **Groups** that can be collapsed.
- The layout follows the Panel's shape: in a tall Panel the Groups are stacked and the
  tiles wrap; in a low, wide strip the Groups sit side by side in one row that scrolls
  sideways (scrollbar or mouse wheel).
- Drag tiles to reorder them or move them to another Group. Drop a tile on **Delete**
  to remove it; **Undo** brings it back for a few seconds.
- Right-click a tile to rename, move or delete it. Right-click a Group name to add,
  rename, reorder or delete Groups.
- **☰** sets the tile size (40–80 px) and turns labels under the tiles on or off.
  These settings, collapsed Groups and the whole Layout survive a restart.
- With a pen, hovering over any tile or control shows its name.
- A tile whose brush, resource or menu command is missing on this machine shows a
  yellow warning triangle, and clicking it only explains what is missing.

### Brush buttons

Drag a brush or tool preset from Painter's Assets window onto a Group. One click on the
tile makes it the active brush, whether the Assets window is open, closed, hidden behind
a tab or floating. Built-in presets, your own presets and `.abr` brushes all work, and
the tile shows the brush's picture.

### Menu buttons

A Menu button runs one of Painter's own menu commands, for example **File → Save**.
Add one with **+ → Menu button**, then either click the command in Painter's menu, or
pick it with **Choose from list…** (a searchable list of all menu commands, submenus
included).

### Workflow buttons

A Workflow button carries out several Steps in Painter with one click, for example
"Fill layer + black mask + Dirt generator + 50% opacity". One **Ctrl+Z** undoes all of
its layer changes. If a Step cannot run, the Workflow stops before it changes anything
and the Panel says why.

New layers go directly above the selected layer (inside its folder, if it is in one),
or at the top of the stack when nothing is selected.

Available Steps:

| Section | Steps |
|---|---|
| Layer | Fill layer, Paint layer, Folder, Smart material, Select layer by name |
| Mask | Black mask, White mask, Smart mask |
| Effect (on the mask or on the layer) | Generator, Filter, Levels, Anchor point, Paint, Fill |
| Setting | Blend mode, Opacity (per channel), Fill content |
| At the end | Brush, Menu command, Save |

For a new Fill or Paint layer you can choose which channels are switched on. A Fill
layer, or a Fill inside a layer or mask, can hold one material, or a value, colour,
resource or anchor point per channel.

### The Workflow editor

- **+ → Workflow button** starts a new Workflow; a **double-click** on a Workflow
  tile (or right-click → **Edit Workflow…**) opens an existing one.
- Steps are shown grouped under the layer they act on. Steps under **Start** act on
  the layer selected when the Button is clicked. Reorder them with the arrows or by
  dragging; a Step dropped where it cannot run snaps back.
- Generators, filters, smart materials, smart masks and other resources are chosen
  from a searchable list, or dragged in from the Assets window.
- A Workflow gets a name from its Steps unless you type your own, and the icon of its
  first Step unless you choose a PNG or JPG.
- The editor marks a Step that still needs a choice (⚠), and **Save** waits until every
  Step is complete.

### Recording

Instead of building a Workflow by hand, record it: **+ → Recorded Workflow**, do the
Steps in Painter while a red **● REC** bar counts them, then press **Stop**. The
recorded Steps open in the editor to check and save. **● Continue** in the editor
records more Steps onto the end of an existing Workflow.

Recording captures new layers with their channels and Fill content, masks, effects,
smart materials and masks, opacity, blend mode, anchor points and selecting an older
layer. Undone changes are left out. Brushes and paint strokes cannot be recorded; add a
brush Step in the editor after **Stop**. The Panel tells you when something you did
(for example moving a layer) cannot be recorded.

### Updates and diagnostics

- Shelf+ checks GitHub for a newer release on start (at most once a day) and with
  **☰ → Check for updates**. The update window offers **Update**, **Later** and
  **Skip this version**.
- **☰ → Copy diagnostics** copies the versions and the recent log, for bug reports.

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
