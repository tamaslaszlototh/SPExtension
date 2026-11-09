# Smart material buttons

A Smart material button puts a smart material into the layer stack: with one click, or
by dragging it onto Painter's Layers window.

## Add a Smart material button

1. Open the Assets window (**Window → Views → Assets**).
2. Drag a smart material onto a Group on the Panel. Drop it between two tiles, or on the
   Group's name.
3. A new tile appears with the smart material's picture. Its name is the smart material's
   name.

You can drag several resources at once: every brush becomes a
[Brush button](brush-buttons.md) and every smart material a Smart material button, in the
order you dragged them. Anything else, such as a material, a smart mask or a filter, is
skipped, and the Panel says *"…" is not a brush, tool preset or smart material.*

## Click it

Click the tile. The smart material goes **above the selected layer**, in the same folder.
With no layer selected, it goes on top of the layer stack. Afterwards the new smart
material folder is selected.

One **Ctrl+Z** takes it out again, as for any Workflow.

Without an open project, the Panel says *Open a project first.*

## Drag it onto the Layers window

Drag the tile out of the Panel onto Painter's **Layers** window. Painter shows its own
drop line, and the smart material lands exactly there, as if you had dragged it from the
Assets window.

Released inside the Panel, the drag works as for any tile: it moves the Button, or deletes
it on **Delete**. See [Drag and drop](panel.md#drag-and-drop).

!!! warning "Being tested"
    Dragging onto the Layers window is new in v1.1.0-alpha.1 and is being tested on
    Painter 11.1 and 12.2. If Painter does not take the drop, use a click instead.

## While recording

During a [Recording](recording.md), clicking a Smart material button records a complete
**Add smart material** Step, with the smart material already chosen. Dragging one onto the
Layers window is recorded like a drag from the Assets window.

## When a smart material is missing

If the smart material is renamed or deleted, or the Layout was made on another machine,
the tile gets a [yellow warning triangle](panel.md#warning-triangles). Clicking it shows
*This smart material is not available on this machine: …* and changes nothing. Such a
tile can only be dragged within the Panel.

!!! note
    Right after Painter starts, it can take up to half a minute until Painter has loaded
    its resources. Until then, Shelf+ does not mark smart materials as missing.
