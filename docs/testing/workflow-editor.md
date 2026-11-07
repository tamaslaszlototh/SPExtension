# Testing the Workflow editor (Shelf+ v0.7.0-rc.1)

This build lets you **make your own Workflows on the Panel** and fix existing ones:

- **+ → Workflow button** in a Group row opens the editor with an empty Workflow.
- A **double-click** on a Workflow button opens it in the editor. One click still runs it, a moment after you click (Shelf+ waits briefly to see whether a second click follows). Right-click → **Edit Workflow…** opens it too.
- The editor shows the Steps grouped under the layer they work on. Steps that act on the layer you have selected when you click the Button sit under **Start**, at the top. Brush, menu command and Save Steps sit under **At the end of the Workflow**.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 15 minutes. Write the results in the [table at the end](#results).

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.7.0-rc.1.zip** from the [v0.7.0-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.7.0-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project. Use a copy of a project you do not mind changing.
6. Click **☰** in the Panel's top right corner. The first line must say **Shelf+ v0.7.0**.

Your own Layout stays as it is. This test adds a few Buttons, and you can delete them afterwards.

## 2. The checks

### A. Build "Fill layer + Black mask + Dirt + Opacity 50%" by hand

1. Click **+** in the *General* row, then **Workflow button**. The editor replaces the Groups.
   - ✅ **Save** is greyed out, and the text above it says *Add a Step first.*
2. Click **+ Add Step → Layer → Fill layer**, then **+ Add Step → Mask → Black mask**.
   - ✅ *Black mask* is indented under *Fill layer*.
3. Click **+ Add Step → Effect → Generator on the mask**.
   - ✅ The row says **Generator ⚠ choose resource**, and Save is greyed out.
4. With that row selected, drag the **Dirt** generator from the Assets window (Generators) onto the editor.
   - ✅ The row now says **Dirt**, and the ⚠ is gone.
5. Click **+ Add Step → Setting → Opacity**. Below the Steps, keep **BaseColor** ticked and set it to **50 %**.
   - ✅ The name at the top reads **Fill layer + Black mask + Dirt + Opacity 50%**.
6. Click **Save**.
   - ✅ The Groups come back, with a new tile at the end of *General*. Its icon is the Fill layer Step's icon.
7. Select a layer in the Layers window and click the new tile **once**.
   - ✅ A Fill layer with a black mask, a Dirt generator in the mask and BaseColor opacity 50% appears above the selected layer.
   - ✅ One **Ctrl+Z** removes all of it.

### B. Reopen it, move Opacity to the Start block

1. **Double-click** the tile from check A.
   - ✅ The editor opens with its four Steps. Nothing new appears in the Layers window: the double-click did not run it.
2. On the **Opacity** row, click **↑** until it is at the top, under **Start: the layer selected when it runs**. Or drag it there.
3. Click **Save**. Select a layer and click the tile once.
   - ✅ The selected layer's BaseColor opacity becomes 50%, and the new Fill layer above it keeps 100%.

### C. Save cannot go above a layer Step

1. Open the editor on any Workflow and add **+ Add Step → At the end → Save** if it has none.
2. Drag the **Save** row above a layer row and let go.
   - ✅ It jumps back to *At the end of the Workflow*, and the Panel says *A Step cannot go there; it was put back.*
3. Drag a **Fill layer** row (a bold row) into the middle of another layer's Steps.
   - ✅ It jumps back too: layers cannot go inside other layers.
4. Click **Cancel**. Nothing is saved.

### D. A Workflow's own icon

1. Double-click a Workflow tile. In the editor, click the icon left of the name, then **Choose image…**, and pick any PNG or JPG on your computer.
2. Click **Save**.
   - ✅ The tile shows your image. It is still there after Painter restarts.
3. Optional: open it again, click the icon → **Use the first Step's icon**, and Save. The tile shows the Step icon again.

### E. Select layer by name

1. Make a new Workflow: **+ Add Step → Layer → Select layer by name**.
   - ✅ The row says **⚠ enter a name**, and Save is greyed out.
2. Select a layer in the Layers window and click **Use selected layer's name**.
   - ✅ The name field shows that layer's name, and Save works.

### F. Delete a Workflow from the editor

1. Open the editor on one of the Workflows you made and click the **bin** next to the name.
   - ✅ You are asked *Delete "…"?*. **No** leaves everything as it was.
2. Click the bin again and answer **Yes**.
   - ✅ The editor closes, the tile is gone, and **Undo** appears for a few seconds. Undo brings the tile back.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened. Write anything odd in **Notes**, even if the check passed, for example flicker, slowness, a drag that would not start, or a Painter warning.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.7.0 | | | |
| A. Build Fill + Black mask + Dirt + Opacity 50%, run it | | | |
| B. Double-click reopens; Opacity into Start | | | |
| C. Save and a layer row snap back | | | |
| D. Own icon from disk | | | |
| E. Select layer by name | | | |
| F. Delete from the editor asks first | | | |

**If something fails:**

1. Click **☰ → Copy diagnostics** right away, before restarting Painter.
2. Paste what it copies into your message. It contains the versions and the recent log.

Send the filled-in table back, for example as a comment on [issue #30](https://github.com/tamaslaszlototh/SPExtension/issues/30).
