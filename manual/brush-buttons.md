# Brush buttons

A Brush button makes a brush or tool preset the active brush with one click.

## Add a Brush button

1. Open the Assets window (**Window → Views → Assets**).
2. Drag a brush or tool preset onto a Group on the Panel. Drop it between two tiles, or on
   the Group's name.
3. A new tile appears with the brush's picture. Its name is the brush's name.

These all work:

- built-in tool presets, such as *Basic Hard*;
- presets you saved yourself;
- `.abr` brushes.

If you drop something that is not a brush, such as a material, no tile is added and the
Panel tells you why.

!!! tip
    **+ → Brush button** in a Group row only reminds you to drag a brush in. Dragging is
    the way to add one.

## Use a Brush button

Click the tile. Within about a second, the brush becomes the active brush.

This works whatever state the Assets window is in: open, closed, hidden behind another
tab, or floating. Shelf+ opens the Assets window if it needs to, and leaves it open.

!!! warning "Painter needs something you can paint on"
    Painter changes the brush only while a **Paint layer** or a **mask** is selected.

    - If a Fill layer with a mask is selected, Shelf+ selects its mask first.
    - If a Fill layer without a mask, or a folder, is selected, the Panel says:
      *Painter changes the brush only while a Paint layer or a mask is selected. Select
      one, then try again.*

## When a brush is missing

Shelf+ finds the brush by its name. If the brush is renamed or deleted, or the Layout was
made on another machine, the tile gets a [yellow warning triangle](panel.md#warning-triangles).
Clicking it shows *This brush is not available on this machine: …* and does not change
the active brush.

!!! note
    Right after Painter starts, it can take up to half a minute until Painter has loaded
    its brushes. Until then, Shelf+ does not mark brushes as missing.
