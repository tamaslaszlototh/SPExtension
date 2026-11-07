# Testing effect, smart material and brush Steps (Shelf+ v0.6.0-rc.1)

This build adds the rest of the Steps a Workflow can have:

- effects (generator, filter, levels, anchor point) on a layer's mask or on the layer itself;
- smart materials and smart masks;
- choosing a brush at the end of a Workflow.

You cannot build your own Workflows on the Panel yet. For this test you paste a ready-made Layout into `layout.json`. It has one Workflow button for each check.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 15 minutes. Write the results in the [table at the end](#results).

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.6.0-rc.1.zip** from the [v0.6.0-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.6.0-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.

## 2. Load the test Layout

1. Open the folder `%APPDATA%\ShelfPlus`: paste that path into the File Explorer address bar.
2. **Keep your own Layout:** copy `layout.json` and rename the copy to `layout.mine.json`. You put it back at the end.
3. Open `layout.json` in Notepad, replace all of its text with the text below (the code box has a copy button on GitHub), and save it.
4. In the line marked `"t6material"`, replace `Rust Coat` with the exact name of any **smart material** from your Assets window (Smart materials). Keep the `resource://starter_assets/` part. If you do not have one called *Rust Coat*, pick one that came with Painter.

```json
{
  "schemaVersion": 1,
  "groups": [
    { "id": "t6steps", "name": "Steps", "buttons": [
      { "id": "t6dirt", "kind": "workflow", "name": "Fill + Black mask + Dirt + Levels", "icon": null, "steps": [
        { "type": "add_layer", "layer": "fill" },
        { "type": "add_mask", "background": "black" },
        { "type": "add_effect", "effect": "generator", "target": "mask", "resource": "resource://starter_assets/mg_dirt/mg_dirt" },
        { "type": "add_effect", "effect": "levels", "target": "mask" } ] },
      { "id": "t6material", "kind": "workflow", "name": "Smart material + Smart mask", "icon": null, "steps": [
        { "type": "add_smart", "smart": "material", "resource": "resource://starter_assets/Rust Coat" },
        { "type": "add_smart", "smart": "mask", "resource": "resource://starter_assets/Dirt" } ] },
      { "id": "t6brush", "kind": "workflow", "name": "Fill + Basic Hard brush", "icon": null, "steps": [
        { "type": "add_layer", "layer": "fill" },
        { "type": "select_brush", "resource": "resource://starter_assets/Basic Hard" } ] },
      { "id": "t6renamed", "kind": "workflow", "name": "Renamed preset", "icon": null, "steps": [
        { "type": "add_layer", "layer": "fill" },
        { "type": "add_mask", "background": "black" },
        { "type": "select_brush", "resource": "resource://starter_assets/Basic Hard XYZ" } ] },
      { "id": "t6anchor", "kind": "workflow", "name": "Anchor point on layer", "icon": null, "steps": [
        { "type": "add_effect", "effect": "anchor", "target": "layer" } ] }
    ] }
  ]
}
```

5. Start Painter and open a project. Use a copy of a project you do not mind changing.
6. In the Panel's top right corner, click **☰**. The first line must say **Shelf+ v0.6.0**.
   - If it says an older version, or Painter showed "Shelf+ v0.6.0 failed to start; reverted to …", stop here.
   - Click **☰ → Copy diagnostics** and send what it copies.
7. The Panel shows one Group, **Steps**, with five tiles. Hover over a tile to see its name.

## 3. The checks

After each check, press **Ctrl+Z** once to undo it, unless the check says otherwise.

### A. Fill layer + black mask + Dirt generator + Levels

1. Click a layer that is not inside a folder.
2. Click **Fill + Black mask + Dirt + Levels**.
   - ✅ A new Fill layer appears directly above the layer you clicked, and it is selected.
   - ✅ It has a **black** mask. In the mask's stack (click the small arrow next to the layer) there is a **Dirt** generator with a **Levels** effect above it.
   - ✅ The History (**Window → Views → History**) got **one** new row.
3. Press **Ctrl+Z** once. ✅ The Fill layer, its mask, the generator and the Levels are all gone.

### B. A smart material, then a smart mask on it

1. Click any layer.
2. Click **Smart material + Smart mask**.
   - ✅ A new folder with the smart material's name appears directly above the layer you clicked, and it is selected.
   - ✅ The folder has a mask with the **Dirt** smart mask inside it.
   - ✅ One Ctrl+Z removes all of it.
3. If a message says the smart material *is not available on this machine*, the name in `layout.json` is not quite right: check step 4 of [Load the test Layout](#2-load-the-test-layout), restart Painter and try again. Write the name you used in the notes.

### C. Fill layer, then a brush at the end

1. Choose some other brush than *Basic Hard* first (for example the Eraser's brush is fine, or any other preset).
2. Click a layer, then click **Fill + Basic Hard brush**.
   - ✅ A new Fill layer appears above the layer you clicked, and it is selected.
   - ✅ Afterwards, the active brush is **Basic Hard**. The Assets window opens or comes to the front for this; that is expected.
3. Press **Ctrl+Z** once. ✅ The Fill layer is gone. (The brush stays Basic Hard; brush changes are not undone.)

### D. A renamed preset

The **Renamed preset** tile refers to a brush called *Basic Hard XYZ*, which does not exist, as if it had been renamed.

1. Click a layer and remember how the layer stack looks.
2. Click **Renamed preset**.
   - ✅ A message on the Panel says: *“Renamed preset” did not start: Step 3 (Select brush): This brush is not available on this machine: resource://starter_assets/Basic Hard XYZ*
   - ✅ **Nothing** changed: no new Fill layer, no new History row.

### E. Anchor point, and an effect that cannot go on the mask

1. Click a layer **without** a mask, then click **Anchor point on layer**.
   - ✅ An **Anchor point** appears in that layer's own stack (not on a mask). Ctrl+Z removes it.
2. Click a **folder**, then click **Anchor point on layer**.
   - ✅ A message on the Panel says *“Anchor point on layer” stopped at Step 1 (Add anchor point to the layer): …* followed by Painter's reason, because a folder has no content of its own. Write the reason in the notes.
   - If instead an anchor point appears, write *folder accepted it* in the notes. That is not a failure.

## 4. Clean up

1. Close Painter.
2. In `%APPDATA%\ShelfPlus`, delete `layout.json` and rename `layout.mine.json` back to `layout.json`.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened. Write anything odd in **Notes**, even if the check passed, for example flicker, slowness, or a Painter warning.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.6.0 | | | |
| A. Fill + black mask + Dirt + Levels (and one Ctrl+Z) | | | |
| B. Smart material + smart mask | | | |
| C. Fill layer, then Basic Hard | | | |
| D. Renamed preset does not start | | | |
| E. Anchor point; folder message | | | |

**If something fails:**

1. Click **☰ → Copy diagnostics** right away, before restarting Painter.
2. Paste what it copies into your message. It contains the versions and the recent log.

Send the filled-in table back, for example as a comment on [issue #29](https://github.com/tamaslaszlototh/SPExtension/issues/29).
