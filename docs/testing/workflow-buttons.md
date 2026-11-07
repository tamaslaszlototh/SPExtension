# Testing Workflow buttons (Shelf+ v0.5.0-rc.1)

This build makes **Workflow buttons** run. A Workflow button does several things in Painter with one click, and one **Ctrl+Z** undoes all of its layer changes.

The *General* Group already has two of them:

- **Save** saves the project.
- **Fill layer + Black mask** adds a Fill layer with a black mask.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 10 minutes. Write the results in the [table at the end](#results).

**What is expected not to work yet:**

- In the **+** menu, *Workflow button* says *(coming soon)* and is greyed out. You cannot make your own Workflows yet.
- If you deleted the *Save* or *Fill layer + Black mask* tile earlier, it does not come back by itself. Close Painter, delete `layout.json` in `%APPDATA%\ShelfPlus` (paste that path into the File Explorer address bar), and start Painter again. This also removes your other tiles.

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.5.0-rc.1.zip** from the [v0.5.0-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.5.0-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project. Use a copy of a project you do not mind changing.
6. In the Panel's top right corner, click **☰**. The first line must say **Shelf+ v0.5.0**.
   - If it says an older version, or Painter showed "Shelf+ v0.5.0 failed to start; reverted to …", stop here.
   - Click **☰ → Copy diagnostics** and send what it copies.

## 2. The checks

### A. A layer selected

1. In the Layers window, click a layer that is **not** inside a folder.
2. Click **Fill layer + Black mask** on the Panel.
   - ✅ A new Fill layer appears directly **above** the layer you clicked.
   - ✅ It has a **black** mask.
   - ✅ The new Fill layer is now the selected layer.
3. Open **Window → Views → History**.
   - ✅ The click added **one** row to the History.
4. Press **Ctrl+Z** once.
   - ✅ The Fill layer and its mask are both gone.

### B. A layer inside a folder

1. Open a folder in the Layers window and click a layer **inside** it. (If the project has no folder, make one first with the folder button of the Layers window and put a layer into it.)
2. Click **Fill layer + Black mask**.
   - ✅ The new Fill layer is **inside the same folder**, directly above the layer you clicked, and it is selected.
3. Press **Ctrl+Z** once. ✅ It is gone.

### C. A folder selected

1. Click the **folder** itself in the Layers window.
2. Click **Fill layer + Black mask**.
   - ✅ The new Fill layer is directly **above the folder**, not inside it, and it is selected.
3. Press **Ctrl+Z** once. ✅ It is gone.

### D. Nothing selected

1. Make sure no layer is selected. (Switching to another texture set and back, or opening the project fresh, usually leaves nothing selected. If you cannot get there, write *could not deselect* in the table and skip this check.)
2. Click **Fill layer + Black mask**.
   - ✅ The new Fill layer appears at the **top** of the layer stack, and it is selected.
3. Press **Ctrl+Z** once. ✅ It is gone.

### E. Save

1. Change something small in the project, so Painter's title bar shows it is unsaved (an `*` after the name).
2. Click **Save** on the Panel.
   - ✅ The project saves: the `*` disappears.

### F. No project open

1. Close the project (**File → Close**), but leave Painter running.
2. Click **Fill layer + Black mask**.
   - ✅ A message on the Panel says *“Fill layer + Black mask” did not start: open a project first.* Nothing else happens.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened. Write anything odd in **Notes**, even if the check passed, for example flicker, slowness, or a Painter warning.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.5.0 | | | |
| A. A layer selected (and one Ctrl+Z) | | | |
| B. A layer inside a folder | | | |
| C. A folder selected | | | |
| D. Nothing selected | | | |
| E. Save | | | |
| F. No project open | | | |

**If something fails:**

1. Click **☰ → Copy diagnostics** right away, before restarting Painter.
2. Paste what it copies into your message. It contains the versions and the recent log.

Send the filled-in table back, for example as a comment on [issue #28](https://github.com/tamaslaszlototh/SPExtension/issues/28).
