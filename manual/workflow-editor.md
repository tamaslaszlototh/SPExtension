# The Workflow editor

The editor takes the place of the Groups on the Panel while it is open.

## Open the editor

- **+ → Workflow button** in a Group row starts a new, empty Workflow.
- **Double-click** a Workflow tile, or right-click it → **Edit Workflow…**, opens an
  existing one.

## How Steps are shown

Steps are grouped under the layer they act on:

**Start: the layer selected when it runs**
:   Steps here act on the layer you have selected when you click the Button. This block is
    shown only when it has Steps.

**Layer blocks**
:   Each Step that creates or picks a layer (Fill layer, Paint layer, Folder, Smart
    material, Select layer by name) starts a block, shown as a bold row. The Steps
    indented under it act on that layer.

**At the end of the Workflow**
:   Brush, Menu command and Save Steps always come last.

Each indented row says in muted italics what it applies to, for example **Generator**
*on mask*.

## Build a Workflow

This example builds *Fill layer + Black mask + Dirt + Opacity 50%*:

1. Click **+ → Workflow button**.
2. **+ Add Step → Layer → Fill layer**.
3. **+ Add Step → Mask → Black mask**. It is indented under *Fill layer*.
4. **+ Add Step → Effect → Generator on mask**. The row says **Generator ⚠ choose
   resource**.
5. With that row selected, click **Choose…** on the **Resource** line below the Steps,
   type `dirt`, pick the Dirt generator, and click **Choose**.
6. **+ Add Step → Setting → Opacity**. Keep **BaseColor** ticked and set it to **50 %**.
7. Click **Save**. A new tile appears at the end of the Group.

## Step settings

Click a row to see its settings below the Steps. What you can set for each Step is in the
[Step reference](steps.md).

### Choosing a resource

Generators, filters, smart materials, smart masks, brushes, materials and textures are
chosen in one of two ways:

- Click **Choose…** and pick from a searchable list of Painter's resources.
- Drag the resource from the Assets window onto the editor, or onto its **Choose…**
  button.

!!! note
    Generators cannot be dragged out of Painter's Assets window. Use **Choose…** for them.

After you choose, the button shows the resource's name. Click it again to choose another
one.

## Reorder and delete Steps

- Use the **↑** and **↓** on a row, or drag the row.
- A Step dropped where it cannot run jumps back, and the Panel says *A Step cannot go
  there; it was put back.* For example, Save cannot go above a layer Step, and a layer
  cannot go inside another layer.
- **X** on a row deletes the Step. Deleting a layer row also deletes the Steps under it,
  after asking.

## Name and icon

- The Workflow gets a name from its Steps, for example *Fill layer + Black mask*. Type in
  the name field to give your own. Clear the field to go back to the automatic name.
- The icon is the first Step's icon. Click the icon left of the name, then **Choose
  image…** to use a PNG or JPG from disk, or **Use the first Step's icon** to go back.

## Save, cancel, delete

- A Step that still needs a choice is marked **⚠**, for example *⚠ choose resource* or
  *⚠ enter a name*. **Save** stays greyed out until every Step is complete. Hover over it
  to see what is missing.
- **Cancel** closes the editor without saving.
- The **bin** next to the name deletes the Workflow after asking. **Undo** brings it back
  for a few seconds.
- **● Continue** records more Steps onto the end of this Workflow. See
  [Recording](recording.md#continue-a-workflow).
