# Workflow buttons

A Workflow button carries out several **Steps** in Painter with one click, for example
*Fill layer + black mask + Dirt generator + 50 % opacity*.

Make one in the [Workflow editor](workflow-editor.md) (**+ → Workflow button**), or
[record one](recording.md) (**+ → Recorded Workflow**).

## Run a Workflow

1. Open a project.
2. In the Layers window, select the layer the Workflow should start from.
3. Click the Workflow's tile **once**.

## One Ctrl+Z undoes it all

All the layer changes of one click are a single entry in Painter's History. Press
++ctrl+z++ once to undo all of them.

Brush changes are not undone, the same as in Painter itself.

## Where new layers go

| What is selected when you click | Where a new layer appears |
|---|---|
| A layer | Directly above it |
| A layer inside a folder | Inside the same folder, directly above it |
| A folder | Directly above the folder, not inside it |
| Nothing | At the top of the layer stack |

The new layer becomes the selected layer.

## The Current layer

Each Step acts on the **Current layer**:

- It starts as the layer selected when you click the Button.
- It changes only when a Step creates a new layer (Fill layer, Paint layer, Folder, Smart
  material) or picks one with **Select layer by name**.

A Step never acts on any other layer. For example, *Black mask* after *Fill layer* puts
the mask on the new Fill layer.

## If a Step cannot run

Before it changes anything, Shelf+ checks the whole Workflow. If a Step cannot run, the
Workflow does **not start** at all, and the Panel says why, for example:

> "Fill + Basic Hard brush" did not start: Step 2 (Select brush) needs a Paint layer or a
> mask: …

Common reasons are no open project, no selected layer, a missing resource or brush, or a
Step that needs a mask on a layer that has none. See
[Troubleshooting](troubleshooting.md#a-workflow-did-not-start) for the full list.
