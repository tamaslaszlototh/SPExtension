# Testing Recording (Shelf+ v0.8.0-rc.1)

This build lets you **record a Workflow**: you do the Steps in Painter while the Panel watches, then you press **Stop** and check the Steps in the editor.

- **+ → Recorded Workflow** in a Group row starts a Recording. A red **● REC** bar appears at the top of the Panel and counts the Steps.
- **Stop** in the REC bar opens the editor with the recorded Steps. Save it as usual.
- **● Continue** at the bottom of the editor records more Steps at the end of the Workflow that is open.
- Brushes cannot be recorded (Painter does not report them). Add them in the editor after Stop.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 15 minutes. Write the results in the [table at the end](#results).

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.8.0-rc.1.zip** from the [v0.8.0-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.8.0-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project. Use a copy of a project you do not mind changing.
6. Click **☰** in the Panel's top right corner. The first line must say **Shelf+ v0.8.0**.

## 2. The checks

### A. Record Fill + black mask + Dirt + opacity

1. Select any layer. Click **+** in the "General" row → **Recorded Workflow**. The **● REC** bar appears and blinks.
2. In Painter: add a **Fill layer**, then a **black mask** on it, then a **generator** on the mask, and choose **Dirt** as the generator.
3. Drag the Fill layer's **opacity** to **50%** (in its row of the layer stack).
4. Set the Fill layer's blend mode to **Multiply**, then press **Ctrl+Z** once.
5. Press **Stop**.
   - Expected: the editor shows **4 Steps**: Fill layer, Black mask, Dirt (generator on mask), Opacity 50%. No blend mode Step.
   - Click the Opacity Step: the value is **exactly 50**.
6. Save it, select another layer and click the new Button. The same layers appear.

### B. Smart mask

1. Start a Recording. Add a Fill layer, then drag a **smart mask** from the Assets window onto it.
2. Press **Stop**. Expected: the last Step says **⚠ choose resource** and is selected. **Save** is blocked.
3. Drag the same smart mask from the Assets window onto the editor. Expected: the Step now shows the smart mask's name, and Save works.

### C. Selecting an older layer

1. Start a Recording. Click a layer that was in the stack before you started (not the one selected at the start).
2. Add a black mask to it, then press **Stop**.
   - Expected: a **“<layer name>” (select layer)** Step comes first, then the Black mask under it.

### D. Painting is not recorded

1. Start a Recording with a **Paint layer** selected. Paint a few strokes.
2. Press **Stop**. Expected: **no Step**, and no message saying something "cannot be recorded".

### E. Continue a Workflow

1. Double-click the Workflow you saved in check A. Click **● Continue**. The REC bar appears.
2. In Painter, add a **white mask** to a new Paint layer, then press **Stop**.
   - Expected: the editor shows the old Steps, then Paint layer and **White mask**.
3. **+ Add Step → Save**. Save the Workflow and click its Button. Expected: it runs and Painter saves the project.

### F. Messages

1. Start a Recording. Move a layer up or down in the stack. Expected: a message says that moving layers cannot be recorded. Press **Stop**.
2. Start a Recording. Close the project. Expected: the REC bar goes away and the editor opens with what was recorded.

If anything goes wrong, click **☰ → Copy diagnostics** and paste it into the issue.

## Results

| Check | Home 11.1.0 | Work 12.2.0 | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.8.0 | | | |
| A. 4 Steps, opacity exactly 50 | | | |
| B. Smart mask marked, drop fills it | | | |
| C. Select layer Step appears | | | |
| D. Painting gives no Step, no message | | | |
| E. Continue, add Save, run | | | |
| F. Messages (move, project close) | | | |
