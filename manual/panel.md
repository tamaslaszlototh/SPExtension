# The Panel

The Panel shows your Buttons as icon tiles, arranged in named Groups. Its top bar holds
**☰** (the Shelf+ menu) and shows short messages from Shelf+.

## Groups

Each Group has a row with:

- an **arrow** that collapses or expands the Group;
- the Group's **name**;
- a **+** that adds a Button to this Group.

Right-click a Group's **name** for these options:

| Option | What it does |
|---|---|
| **New Group…** | Adds an empty Group right after this one |
| **Rename…** | Renames the Group |
| **Move up** / **Move down** | Changes the Group's place. In a wide Panel these are **Move left** / **Move right** |
| **Delete Group** | Deletes the Group. Only an empty Group can be deleted |

## Tiles

- **Click** a tile to run its Button.
- **Right-click** a tile for **Rename…**, **Move to →** (another Group) and **Delete**.
  Workflow buttons also have **Edit Workflow…**.
- **Double-click** a Workflow tile to open it in the [Workflow editor](workflow-editor.md).

!!! note "Why a Workflow runs a moment after the click"
    Shelf+ waits briefly to see whether a second click follows, so a double-click can open
    the editor instead of running the Workflow.

## Drag and drop

- Drag a tile to a new place in its Group, or into another Group. An orange line shows
  where it will land.
- Drag a [Smart material button](smart-material-buttons.md) out of the Panel onto
  Painter's Layers window to put its smart material there.
- When you start dragging, a **Delete** button with a trash icon appears in the top bar.
  Drop the tile on it to delete the Button.
- In a wide Panel, hold a dragged tile near the left or right edge to scroll the row.

## Undo a delete

After you delete a Button, the top bar shows *Deleted "…". **Undo*** for about
5 seconds. Click **Undo** to bring the Button back to its old place. After that, the
delete is final.

## Tall and wide Panels

The layout follows the Panel's shape:

=== "Tall Panel"

    When the Panel is docked at a side of Painter, the Groups are stacked top to bottom
    and the tiles wrap into more rows. Make the Panel wider to fit more tiles in each
    row.

=== "Wide strip"

    When the Panel is a low, wide strip (at least about twice as wide as it is high), the
    Groups sit side by side in one row, with each Group's name above its tiles. If not
    everything fits, scroll the row sideways with the scrollbar or the mouse wheel.

## The ☰ menu

| Item | What it does |
|---|---|
| **Shelf+ vX.Y.Z** | Shows the version you are running |
| **Tile size** | A slider from 40 to 80 px. The tiles resize while you drag it |
| **Show labels** | Shows each Button's name under its tile |
| **Check for updates** | See [Updates & diagnostics](updates.md) |
| **Copy diagnostics** | Copies versions and the recent log for a bug report |

The tile size, labels, collapsed Groups and the whole Layout are saved and survive a
restart.

## Hover names with a pen

With a pen, hold it above the tablet over any tile or control for about half a second.
Its name appears, for example the Button's name, or *Add a Button to Layers* over a **+**.

## Warning triangles

A Brush, Smart material or Menu button tile with a small **yellow warning triangle**
cannot run here: its brush, smart material or menu command is missing. Hover over it to see *(not available on this
machine)* or *(not available in this Painter version)*. Clicking it only explains what is
missing and changes nothing. See [Troubleshooting](troubleshooting.md#a-tile-has-a-yellow-warning-triangle).
