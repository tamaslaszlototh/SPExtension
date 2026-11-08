# Recording

Instead of building a Workflow by hand, you can record it: do the Steps in Painter while
the Panel watches, then check them in the editor.

## Record a Workflow

1. Open a project and select the layer to start from.
2. Click the **+** of a Group, then **Recorded Workflow**. A red, blinking **● REC** bar
   appears at the top of the Panel and counts the Steps.
3. Work in Painter as usual: add layers, masks, effects, change opacity and so on.
4. Click **Stop** in the REC bar.
5. The editor opens with the recorded Steps. Check them, fix anything marked ⚠, and click
   **Save**.

If you close the project during a Recording, the Recording stops and the editor opens
with what was recorded so far.

## What is recorded

- New Fill layers, Paint layers and folders, with their switched-on channels;
- a new Fill layer's content: colour, value, resource, material or anchor point per
  channel;
- masks, smart masks and smart materials;
- effects: generators, filters, levels, anchor points (with their names), Paint and Fill;
- opacity and blend mode changes;
- channel or content changes on an **existing** Fill or Paint layer, as a
  [Fill content](steps.md#fill-content) Step;
- selecting a layer that existed before the Recording, as a
  [Select layer by name](steps.md#select-layer-by-name) Step.

Changes you undo with ++ctrl+z++ during the Recording are left out.

## What is not recorded

| Not recorded | What to do |
|---|---|
| **Brushes** | Painter does not report them. Add a [Brush Step](steps.md#at-the-end) in the editor after **Stop** |
| **Paint strokes** | What you paint is not part of a Workflow |
| **Moving** layers | The Panel says *Moving layers cannot be recorded, so it was skipped.* |
| **Deleting** existing layers or effects | Skipped, with a message |
| **Renaming** existing layers | Skipped, with a message |
| **Changing an existing effect** | Skipped, with a message |
| Changes in **another texture set** | A Workflow works on one texture set |

## After Stop

Some things cannot be read back from Painter exactly. For example, a smart mask's row may
say **⚠ choose resource**. The incomplete Step is selected for you: drop the same
smart mask from the Assets window onto the editor, or click **Choose…**.

## Continue a Workflow

To add more Steps to the end of an existing Workflow:

1. Double-click the Workflow's tile to open it in the editor.
2. Click **● Continue**. The REC bar appears.
3. Do the new Steps in Painter, then click **Stop**.
4. The editor shows the old Steps followed by the new ones. Click **Save**.
