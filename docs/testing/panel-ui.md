# Testing the Panel UI (Shelf+ v0.2.0-rc.1)

This build adds the real **Panel**: Groups of icon tiles that you can collapse, a layout that adapts to the Panel's shape, drag and drop, delete with Undo, right-click menus, and hover names for the pen.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 20 minutes. Write the results in the [table at the end](#results).

**What is expected not to work yet:**

- Clicking a Button does nothing.
- In the **+** menu, every item says *(coming soon)* and is greyed out.

Neither of these is a failure.

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.2.0-rc.1.zip** from the [v0.2.0-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.2.0-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter. If the Shelf+ Panel is not visible, open it from **Window → Views → Shelf+**.
6. In the Panel's top right corner, click **☰**. The first line must say **Shelf+ v0.2.0**.
   - If it says v0.1.0, or the Panel shows an error, stop here.
   - Click **☰ → Copy diagnostics** and send what it copies.

## 2. Load the test Layout

The default Layout has only two Buttons. That is too few to see the » overflow menu, so load a test Layout with 12 Buttons in 4 Groups. Its Buttons do nothing when clicked, just like the default ones.

1. Close Painter.
2. Open the folder `%APPDATA%\ShelfPlus`: paste that path into the File Explorer address bar.
3. Open `layout.json` in Notepad.
4. Replace all of its text with the text below (the code box has a copy button on GitHub).
5. Save the file.

```json
{
  "schemaVersion": 1,
  "groups": [
    { "id": "t1general", "name": "General", "buttons": [
      { "id": "t1save", "kind": "workflow", "name": "Save", "icon": null, "steps": [ { "type": "save" } ] },
      { "id": "t1fillblk", "kind": "workflow", "name": "Fill layer + Black mask", "icon": null,
        "steps": [ { "type": "add_layer", "layer": "fill" }, { "type": "add_mask", "background": "black" } ] }
    ] },
    { "id": "t2layers", "name": "Layers", "buttons": [
      { "id": "t2fill", "kind": "workflow", "name": "Fill layer", "icon": null, "steps": [ { "type": "add_layer", "layer": "fill" } ] },
      { "id": "t2paint", "kind": "workflow", "name": "Paint layer", "icon": null, "steps": [ { "type": "add_layer", "layer": "paint" } ] },
      { "id": "t2folder", "kind": "workflow", "name": "Folder", "icon": null, "steps": [ { "type": "add_layer", "layer": "folder" } ] },
      { "id": "t2multiply", "kind": "workflow", "name": "Multiply blend", "icon": null, "steps": [ { "type": "set_blend", "blend": "Multiply" } ] }
    ] },
    { "id": "t3masks", "name": "Masks", "buttons": [
      { "id": "t3black", "kind": "workflow", "name": "Black mask", "icon": null, "steps": [ { "type": "add_mask", "background": "black" } ] },
      { "id": "t3white", "kind": "workflow", "name": "White mask", "icon": null, "steps": [ { "type": "add_mask", "background": "white" } ] },
      { "id": "t3levels", "kind": "workflow", "name": "Mask levels", "icon": null, "steps": [ { "type": "add_effect", "effect": "levels", "target": "mask" } ] }
    ] },
    { "id": "t4effects", "name": "Effects", "buttons": [
      { "id": "t4levels", "kind": "workflow", "name": "Layer levels", "icon": null, "steps": [ { "type": "add_effect", "effect": "levels", "target": "layer" } ] },
      { "id": "t4anchor", "kind": "workflow", "name": "Anchor point", "icon": null, "steps": [ { "type": "add_effect", "effect": "anchor", "target": "layer" } ] },
      { "id": "t4select", "kind": "workflow", "name": "Select Base", "icon": null, "steps": [ { "type": "select_layer", "name": "Base" } ] }
    ] }
  ]
}
```

6. Start Painter. The Panel now shows **General, Layers, Masks, Effects**, with green tiles carrying two letters (for example *FL* for *Fill layer*).
7. **To go back to the default Layout** later, close Painter and delete `layout.json`. Shelf+ copies the default in on the next start.

## 3. The checks

Use the **mouse** for checks A–D, and the **pen** for check E.

### A. View settings survive a restart

1. Click the small arrow left of **Masks**. Its tiles disappear and the arrow points right.
2. Click **☰ → Tile size → 64 px**. The tiles get bigger.
3. Click **☰ → Show labels**. Names appear under the tiles.
4. Close Painter completely and start it again.
5. ✅ **Pass:** Masks is still collapsed, the tiles are still 64 px, and the labels are still on.
6. Put it back for the next checks:
   - Expand Masks.
   - Set **☰ → Tile size → 48 px**.
   - Turn **Show labels** off.

### B. Tall and flat layout

1. **Tall:** dock the Panel on the right side of Painter, so it is tall and narrow.
   - ✅ The Groups are stacked top to bottom.
   - ✅ The tiles wrap into more rows when the Panel is narrow.
   - ✅ When you make the Panel wider, more tiles fit in each row.
2. **Flat:** make the Panel float. Drag it out by its title bar, or double-click the title bar.
3. Resize the floating Panel into a low, wide strip: about one tile high, and at least twice as wide as it is high.
   - ✅ The Groups now sit side by side in one row.
4. Make the strip narrower, until not everything fits.
   - ✅ A **»** button appears at the right end.
   - ✅ Clicking **»** lists the Buttons that did not fit, under their Group names.
   - ✅ A Group that does not fit at all is also listed there.
5. Make the strip wide again. With the test Layout, the whole row needs about 1300 px, roughly two-thirds of a Full HD screen.
   - ✅ The **»** button disappears, and all Buttons are back in the row.

### C. Drag, delete, Undo

1. Drag the **Paint layer** tile from Layers and drop it between two tiles of **General**.
   - ✅ An orange line shows where it will land while you drag.
   - ✅ After you drop it, the tile is in General at that spot.
2. Drag a tile within its own Group to a new position.
   - ✅ The order changes.
3. Start dragging **Folder**. While you drag, a **Delete** button with a trash icon appears at the top of the Panel, next to ☰.
4. Drop Folder on the Delete button.
   - ✅ Folder is gone.
   - ✅ "Deleted "Folder". **Undo**" shows at the top for about 5 seconds.
5. Click **Undo** in time.
   - ✅ Folder comes back in its old place.
6. Delete a tile again and do **not** click Undo.
   - ✅ The Undo message disappears after about 5 seconds and the tile stays deleted.
7. Right-click a tile and try **Rename…**, **Move to → (a Group)** and **Delete**.
   - ✅ Each one works.
   - ✅ Delete also offers Undo.
8. Restart Painter.
   - ✅ The Panel looks the same as before the restart: the moves, deletes and renames were saved.

### D. Groups from the right-click menu

Right-click a Group **name** (for example *Layers*), then try each item below.

1. **New Group…:** type a name and press OK.
   - ✅ The new, empty Group appears right after the one you clicked.
2. **Rename…** on the new Group.
   - ✅ The name changes.
3. **Move up** and **Move down**.
   - ✅ The Group changes place.
   - When the Panel is flat, these are called **Move left** and **Move right**.
   - ✅ The first Group cannot move up, and the last cannot move down: those items are greyed out.
4. **Delete Group** on a Group that has Buttons.
   - ✅ It is greyed out.
5. **Delete Group** on your new empty Group.
   - ✅ The Group is removed.
6. Click **+** in any Group row.
   - ✅ A menu opens with *Brush button*, *Menu button* and *Workflow button*, all marked *(coming soon)*.
7. Restart Painter.
   - ✅ The Groups are as you left them.

### E. Hover names with the pen

Hold the pen **above** the tablet, not touching it. Rest it over each item below for about a second.

| Item | Expected name |
|---|---|
| A tile | The Button's name, for example *Fill layer* |
| The arrow left of a Group name | *Collapse Layers* or *Expand Layers* |
| A Group name | *Layers (right-click for Group options)* |
| The **+** in a Group row | *Add a Button to Layers* |
| **☰** | *Shelf+ menu* |
| **»**, when the Panel is flat | *More Buttons* |
| **Undo**, right after a delete | *Bring back the deleted Button* |

- ✅ **Pass:** every item shows its name after about half a second.
- ✅ The name disappears when you move the pen away.
- ✅ The tile under the pen is still highlighted, as with the mouse.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened. Write anything odd in **Notes**, even if the check passed, for example flicker, slowness, or a Painter warning.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.2.0 | | | |
| A. View settings survive a restart | | | |
| B. Tall and flat layout, » menu | | | |
| C. Drag, delete, Undo | | | |
| D. Groups from the right-click menu | | | |
| E. Hover names with the pen | | | |

**If something fails:**

1. Click **☰ → Copy diagnostics** right away, before restarting Painter.
2. Paste what it copies into your message. It contains the versions and the recent log.

Send the filled-in table back, for example as a comment on [issue #25](https://github.com/tamaslaszlototh/SPExtension/issues/25).
