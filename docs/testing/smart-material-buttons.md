# Testing Smart material buttons (Shelf+ v1.1.0-alpha.1)

This build adds **Smart material buttons**. Drag a smart material from the Assets window onto the Panel. From then on, one click on its tile puts the smart material above the selected layer, and dragging the tile onto Painter's Layers window puts it where you drop it.

Check F is also the **probe** of issue #47: does Painter's Layers window take a drag that Shelf+ starts? Its result decides whether dragging stays in the feature.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 20 minutes.

**Later:** Shelf+ does not offer updates from an alpha build to the final v1.1.0 (they have the same version number). When v1.1.0 is out, install it by hand as in step 1. Write the results in the [table at the end](#results).

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v1.1.0-alpha.1.zip** from the [v1.1.0-alpha.1 release page](https://github.com/tamaslaszlototh/ShelfPlus/releases/tag/v1.1.0-alpha.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project. Use a copy of a project that may change.
6. In the Panel's top right corner, click **☰**. The first line must say **Shelf+ v1.1.0**.
   - If it says an older version, or Painter showed "Shelf+ v1.1.0 failed to start; reverted to …", stop here.
   - Click **☰ → Copy diagnostics** and send what it copies.

## 2. The checks

### A. Dragging smart materials onto the Panel

1. Open the Assets window (**Window → Views → Assets**). Drag a built-in smart material (for example *Rust Iron*) onto a Group. Drop it between two tiles, or on the Group's name.
   - ✅ A new tile appears where you dropped it, with the smart material's picture.
   - ✅ Hover over the tile: its name is the smart material's name.
2. Do the same with a smart material you saved yourself.
3. Select a brush, a smart material and a material together in the Assets window (Ctrl+click), and drag all three onto a Group.
   - ✅ A Brush button and a Smart material button appear, in the order you selected them.
   - ✅ The Panel says the material is *not a brush, tool preset or smart material*.
4. Drag a smart mask onto a Group.
   - ✅ No tile is added, with the same message.

### B. Clicking a Smart material button

1. Select a layer in the middle of the layer stack. Click the Smart material button.
   - ✅ The smart material appears **right above** the selected layer, and its folder is selected.
   - ✅ **Ctrl+Z** once removes it completely. The History shows one row, *Shelf+: Add smart material*.
2. Select a layer **inside a folder**, and click again.
   - ✅ The smart material goes into that folder, above the selected layer.
3. Click on the empty area of the Layers window so that nothing is selected (if Painter allows it), and click again.
   - ✅ The smart material goes on top of the layer stack.
4. Close the project (**File → Close**) and click the tile.
   - ✅ The Panel says *Open a project first.* Nothing else happens.

### C. While recording

1. Open the project again. In a Group row, click **+ → Recorded Workflow**.
2. Click the Smart material button.
3. Drag a smart material from the **Assets window** onto the Layers window.
4. Drag the Smart material button's **tile** from the Panel onto the Layers window (skip this if check F fails).
5. Click **Stop**.
   - ✅ The editor shows three **Add smart material** Steps (two if you skipped step 4). Both have their smart material chosen; neither says *⚠ choose resource*.
6. Close the editor without saving.

### D. After a restart

1. Restart Painter. Watch the Panel while Painter starts up.
   - ✅ No Smart material button shows the yellow warning triangle, not even for a moment.
2. Open a project and click each Smart material button once.
   - ✅ Each one still works, as in check B.

### E. A missing smart material

1. Close Painter.
2. Open `%APPDATA%\ShelfPlus\layout.json` in Notepad. Find a Smart material button: it has `"kind": "smart_material"` and a `"resource"` line.
3. Add `XYZ` to the end of the name inside the quotes, for example `"resource://starter_assets/Rust Iron XYZ",`. Save the file.
4. Start Painter and open a project.
   - ✅ Once Painter has loaded its resources (up to half a minute), the tile has a yellow warning triangle. Hovering over it says *(not available on this machine)*.
   - ✅ Clicking it only shows *This smart material is not available on this machine: …*. The layer stack does not change.
   - ✅ Dragging it onto the Layers window does nothing there. Within the Panel it still moves.
5. To clean up, drag that tile onto **Delete**.

### F. Dragging onto the Layers window (the probe)

1. Drag a Smart material button out of the Panel onto Painter's **Layers** window, and hold it over the stack without releasing.
   - ✅ Painter shows its own drop line, as when you drag from the Assets window.
2. Release it between two layers.
   - ✅ The smart material lands exactly where the line was.
   - ✅ The tile is still on the Panel, in its old place.
3. Repeat, releasing it **on** a folder, and at the very top and bottom of the stack.
4. Drag the tile within the Panel to another place, and onto **Delete**.
   - ✅ It moves and deletes as before. No new tile appears.

If step 1 or 2 fails, note **exactly** what you saw: no drop line, a "forbidden" cursor, a drop that does nothing, or something different landing. Then click **☰ → Copy diagnostics** and send it along.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v1.1.0 | | | |
| A. Drag smart materials in | | | |
| B. Click | | | |
| C. While recording | | | |
| D. After a restart | | | |
| E. A missing smart material | | | |
| F. Drag onto the Layers window | | | |

**If something fails:** click **☰ → Copy diagnostics** right away, before restarting Painter, and paste what it copies into your message.

Send the filled-in table back as a comment on [issue #47](https://github.com/tamaslaszlototh/ShelfPlus/issues/47).
