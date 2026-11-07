# Testing Recording (Shelf+ v0.8.3-rc.1)

This build lets you **record a Workflow**: you do the Steps in Painter while the Panel watches, then you press **Stop** and check the Steps in the editor.

- **+ → Recorded Workflow** in a Group row starts a Recording. A red **● REC** bar appears at the top of the Panel and counts the Steps.
- **Stop** in the REC bar opens the editor with the recorded Steps. Save it as usual.
- **● Continue** at the bottom of the editor records more Steps at the end of the Workflow that is open.
- A new Fill or Paint layer's switched-on channels, and a Fill layer's content (colour, value, resource, material), are recorded too. What you paint onto a Paint layer is not.
- New in v0.8.3: an **anchor point** keeps its name, a Fill channel can use an anchor point as its source, and changing the channels or content of an **existing** Fill or Paint layer becomes a **Fill content** Step.
- Brushes cannot be recorded (Painter does not report them). Add them in the editor after Stop.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 15 minutes. Write the results in the [table at the end](#results).

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.8.3-rc.1.zip** from the [v0.8.3-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.8.3-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project. Use a copy of a project you do not mind changing.
6. Click **☰** in the Panel's top right corner. The first line must say **Shelf+ v0.8.3**.

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
2. Start a Recording, add a Fill layer, then close the project (**File → Close**). Expected: the REC bar goes away and the editor opens with what was recorded (the Fill layer).
3. If the project has several texture sets: start a Recording, switch to another texture set and add a layer there. Expected: a message says changes in another texture set cannot be recorded, and after Stop that layer is not among the Steps.

If anything goes wrong, click **☰ → Copy diagnostics** right away, before restarting Painter, and paste it into your message. Send the filled-in table back, for example as a comment on [issue #31](https://github.com/tamaslaszlototh/SPExtension/issues/31).

A Hungarian version of this guide is in [recording.hu.md](recording.hu.md).

### G. A new layer's channels and content

1. Start a Recording and add a **Fill layer**.
2. In the Fill layer's properties, switch off the **Height** and **Metallic** channels.
3. Set **BaseColor** to a strong red and **Roughness** to **0.9**.
4. Drag a texture or procedural (for example *Clouds*) from the Assets window onto a third channel (for example **Normal**).
5. Also add a **Paint layer**, and leave only **BaseColor** switched on there.
6. Press **Stop** and click the Fill layer's row.
   - Expected: under **Channels**, Height and Metallic are not ticked.
   - Expected: **Content** is **Per channel**: BaseColor red, Roughness 0.9, the third channel the resource you chose.
   - Expected: the Paint layer's row has only BaseColor ticked.
   - Note it if the red is lighter or darker than the one you picked, or if a value is missing.
7. Save it, select another layer and click the new Button once. Expected: the new Fill and Paint layers have the same channels and values as recorded.
8. Optional: in a new Recording, switch a Fill layer to **Material** and drop a material into it. Expected: after Stop the row says **Fill layer: <material name>**.

**Important:** after this check, click **☰ → Copy diagnostics** and send the text even if everything worked. It shows how Shelf+ read the colours from Painter.

### H. Anchor points and an existing layer's Fill content

You need a project with an **existing Fill layer** and an **existing anchor point** (any layer's content or mask; right-click → *Add anchor point* makes one). Use a copy of the project.

1. Select the existing Fill layer. Start a Recording.
2. In the Fill layer's properties, click **BaseColor**, open the **Anchor points** tab and choose the existing anchor point.
3. Press **Stop**.
   - Expected: a **Start** block (or a *select layer* block) with a **Fill content** Step. Its row says **BaseColor anchor “<name>”**, with the anchor point's name.
   - Click the Step: under **Content**, BaseColor is **Anchor point** with that name.
4. Save it. Undo the change in Painter (or open the copy again), select the same Fill layer and click the new Button once.
   - Expected: BaseColor uses the anchor point again.
5. Start a new Recording. Add an **anchor point** to any layer and rename it **Edges**. Then add a **Fill layer** and set its **Height** source to **Edges** (*Anchor points* tab). Press **Stop**.
   - Expected: the anchor point's row says **Anchor point “Edges”**; the Fill layer's row says **anchor “Edges”**.
6. Save it, undo the Recording's changes in Painter, select a layer and click the new Button. Expected: it works.
7. Click it a second time. Expected: nothing changes, and the message says *An anchor point named “Edges” already exists.*

**Important:** after this check, click **☰ → Copy diagnostics** and send the text even if everything worked. It shows how Shelf+ read the anchor point from Painter.

## Results

| Check | Home 11.1.0 | Work 12.2.0 | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.8.3 | | | |
| A. 4 Steps, opacity exactly 50 | | | |
| B. Smart mask marked, drop fills it | | | |
| C. Select layer Step appears | | | |
| D. Painting gives no Step, no message | | | |
| E. Continue, add Save, run | | | |
| F. Messages (move, project close, other texture set) | | | |
| G. A new layer's channels and content (colour, value, resource, material) | | | |
| H. Anchor point source on an existing Fill layer; "Edges" runs once, then refuses | | | |
