# Testing the Workflow editor (Shelf+ v0.7.6-rc.1)

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
2. Download **ShelfPlus-v0.7.6-rc.1.zip** from the [v0.7.6-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.7.6-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project. Use a copy of a project you do not mind changing.
6. Click **☰** in the Panel's top right corner. The first line must say **Shelf+ v0.7.6**.

Your own Layout stays as it is. This test adds a few Buttons, and you can delete them afterwards.

## 2. The checks

### A. Build "Fill layer + Black mask + Dirt + Opacity 50%" by hand

1. Click **+** in the *General* row, then **Workflow button**. The editor replaces the Groups.
   - ✅ **Save** is greyed out, and the text above it says *Add a Step first.*
2. Click **+ Add Step → Layer → Fill layer**, then **+ Add Step → Mask → Black mask**.
   - ✅ *Black mask* is indented under *Fill layer*.
3. Click **+ Add Step → Effect → Generator on the mask**.
   - ✅ The row says **Generator ⚠ choose resource**, and Save is greyed out.
4. With that row selected, click the **Choose…** button on the **Resource** line below the Steps. Type `dirt` in the search box. (Generators cannot be dragged out of the Assets window, so this list is the way to choose one.)
   - ✅ The list shows Painter's resources whose name contains *dirt*, each with its type after it.
   - Pick the **Dirt generator**: hover the rows, and choose the one whose address ends in `mg_dirt`. Click **Choose**.
   - ✅ The row now says **Dirt**, the ⚠ is gone, and the button now reads **Dirt** instead of *Choose…*.
   - Write down in Notes what type the list showed next to it.
   - Click the **Dirt** button again: ✅ the list opens again, so you could pick another one. Click **Cancel**.
5. Click **+ Add Step → Setting → Opacity**. Below the Steps, keep **BaseColor** ticked and set it to **50 %**.
   - ✅ The name at the top reads **Fill layer + Black mask + Dirt + Opacity 50%**.
6. Click **Save**.
   - ✅ The Groups come back, with a new tile at the end of *General*. Its icon is the Fill layer Step's icon.
7. Select a layer in the Layers window and click the new tile **once**.
   - ✅ A Fill layer with a black mask, a Dirt generator in the mask and BaseColor opacity 50% appears above the selected layer.
   - ✅ In the new Fill layer's properties **every channel is switched on**, as when you add a Fill layer in Painter yourself.
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

### F. A smart mask dropped from the Assets window

1. Make a new Workflow: **+ Add Step → Layer → Fill layer**, then **+ Add Step → Mask → Smart mask**.
   - ✅ The smart mask row says **Smart mask ⚠ choose resource**.
2. With that row selected, drag any **smart mask** from the Assets window (Smart masks) onto the editor.
   - ✅ The row now shows the smart mask's name, and the ⚠ is gone.
   - If the drag does not start or nothing changes, write down which smart mask you tried.
3. Click **Cancel**.

### G. A new layer's channels and content

1. Make a new Workflow: **+ Add Step → Layer → Fill layer**, and click the **Fill layer** row.
   - ✅ Below the Steps, **Channels** lists your texture set's channels, all ticked.
2. Untick **Height**. Set **Content** to **Per channel**.
   - ✅ Each ticked channel gets a row: **Value** with a colour button (BaseColor, Normal…) or a number (Roughness, Metallic, Height…).
   - ✅ **Normal** starts with the flat normal colour **#8080ff** (light blue-violet), as in Painter.
   - ✅ The numbers stay inside the channel's own range: **Height** goes from **−1 to 1** and starts at 0; Roughness and Metallic go from 0 to 1.
   - If a channel allows other values in Painter's own Fill layer properties than here (lower, higher, or another scale), write the channel and its range in Notes.
3. Click the **BaseColor** colour button and pick a strong red. Set **Roughness** to **0.9**.
4. On the **Normal** row (or any other channel), switch **Value** to **Resource**, click **Choose…**, search for a texture or procedural (for example `clouds`) and pick one.
   - ✅ The button now shows the name of what you picked.
   - Also try the other way: on another channel switch to **Resource**, and drag a texture from the Assets window (Textures) **onto its Choose… button**. ✅ The button shows the texture's name.
5. Click **Save**. Select a layer and click the new tile once.
   - ✅ The new Fill layer's properties show Height switched off, BaseColor red, Roughness 0.9, and your resource on the channel from step 4.
   - Write down in Notes if the red looks lighter or darker than the one you picked.
6. Open it again (double-click). On the Fill layer row set **Content** to **One material**, click **Choose…** and pick any material. Save and run it.
   - ✅ The row reads **Fill layer: <material name>**, and the new layer shows that material.
7. Make a Workflow with **Paint layer**, untick all channels except **BaseColor**, save and run it.
   - ✅ The new Paint layer has only BaseColor switched on. (A Paint layer has no Content setting.)

### H. Paint and Fill inside a layer

This is what Painter's right-click **Add paint** / **Add fill** on a layer makes: a Paint or Fill shown indented under the layer.

1. Make a new Workflow: **+ Add Step → Layer → Fill layer**, then **+ Add Step → Effect → Paint on the layer**, then **+ Add Step → Mask → Black mask**, then **+ Add Step → Effect → Fill on the mask**.
   - ✅ The rows read **Fill layer**, **├ Paint**, **├ Black mask**, **└ Fill**.
2. Save it, select a layer and click the tile once.
   - ✅ The new Fill layer has a **Paint** inside it (open the layer's arrow in the Layers window), and its mask has a **Fill** inside it, as if you had used Add paint and Add fill yourself.
   - ✅ One **Ctrl+Z** removes all of it.
3. Open it again (double-click) and click the **└ Fill** row (the Fill on the mask). Set **Content** to **Value** and the value to **0.3**. Save and run it.
   - ✅ The mask's Fill is a dark grey (0.3): the layer shows through only faintly.
4. Open it again, set the mask Fill's **Content** to **Resource**, click **Choose…** (or drop a procedural from the Assets window onto it) and pick e.g. a *Clouds* procedural. Save and run it.
   - ✅ The mask's Fill uses that resource.
5. Add **+ Add Step → Effect → Fill on the layer** under the Fill layer and click it.
   - ✅ It has the same **Channels** and **Content** settings as a Fill layer (check G).
   - Set **Content** to **Per channel**, BaseColor to a strong blue. Save and run it.
   - ✅ The Fill inside the layer is blue, on top of the Fill layer's own colour.

### I. Delete a Workflow from the editor

1. Open the editor on one of the Workflows you made and click the **bin** next to the name.
   - ✅ You are asked *Delete "…"?*. **No** leaves everything as it was.
2. Click the bin again and answer **Yes**.
   - ✅ The editor closes, the tile is gone, and **Undo** appears for a few seconds. Undo brings the tile back.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened. Write anything odd in **Notes**, even if the check passed, for example flicker, slowness, a drag that would not start, or a Painter warning.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.7.6 | | | |
| A. Build Fill + Black mask + Dirt + Opacity 50% (Dirt chosen from the list), run it | | | |
| B. Double-click reopens; Opacity into Start | | | |
| C. Save and a layer row snap back | | | |
| D. Own icon from disk | | | |
| E. Select layer by name | | | |
| F. Smart mask dropped from the Assets window | | | |
| G. Layer channels; per-channel colour, value and resource; one material | | | |
| H. Paint and Fill inside a layer; a Fill's value, resource and channels | | | |
| I. Delete from the editor asks first | | | |

**If something fails:**

1. Click **☰ → Copy diagnostics** right away, before restarting Painter.
2. Paste what it copies into your message. It contains the versions and the recent log.

Send the filled-in table back, for example as a comment on [issue #30](https://github.com/tamaslaszlototh/SPExtension/issues/30).
