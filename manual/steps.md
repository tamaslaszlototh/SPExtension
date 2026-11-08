# Step reference

These are all the Steps in **+ Add Step**, by section. "Current layer" is the layer a Step
acts on (see [The Current layer](workflow-buttons.md#the-current-layer)).

## Layer

These Steps create or pick a layer. It becomes the Current layer, and starts a new block
in the editor.

### Fill layer

Adds a Fill layer [above the selected layer](workflow-buttons.md#where-new-layers-go).

- **Channels**: which of the texture set's channels are switched on. All are on by
  default, as in Painter.
- **Content**:
    - **Painter's default**: an empty Fill layer.
    - **One material**: click **Choose…** and pick a material.
    - **Per channel**: for each switched-on channel, a **Value** (a colour, or a number
      within the channel's range), a **Resource** (a texture or procedural), or an
      **Anchor point** by name.

### Paint layer

Adds a Paint layer. You can choose its **Channels**. A Paint layer has no Content setting.

### Folder

Adds an empty folder.

### Smart material

Adds a smart material, chosen with **Choose…** or dropped from the Assets window. It
appears as a folder named after the smart material.

### Select layer by name

Makes an existing layer the Current layer. Type its exact name, or select the layer in
Painter and click **Use selected layer's name**.

!!! warning
    If several layers have the same name, the Workflow stops at this Step. Rename one of
    them.

## Mask

These Steps add a mask to the Current layer.

| Step | What it adds |
|---|---|
| **Black mask** | A black mask: the layer is hidden until you paint or generate on the mask |
| **White mask** | A white mask: the layer is fully visible |
| **Smart mask** | A smart mask, chosen with **Choose…** or dropped from the Assets window |

## Effect

Each effect goes either **on mask** (into the Current layer's mask) or **on layer** (into
the layer's own content). An effect on mask needs a layer that has a mask. Add a Mask Step
before it.

| Step | What it adds | Settings |
|---|---|---|
| **Generator** | A generator, such as Dirt | The generator, with **Choose…** |
| **Filter** | A filter | The filter, with **Choose…** |
| **Levels** | A Levels effect | None |
| **Anchor point** | An anchor point | **Name**: leave empty for Painter's default name, or type one that later Steps can refer to |
| **Paint** | A Paint inside the layer or mask, as Painter's **Add paint** does | None |
| **Fill** | A Fill inside the layer or mask, as Painter's **Add fill** does | See below |

A **Fill on layer** has the same **Channels** and **Content** settings as a Fill layer.
A **Fill on mask** takes one grey **Value**, one **Resource** or an **Anchor point**.

!!! note "Anchor point names must be unique"
    A Workflow does not start if an anchor point with the same name already exists. Run a
    Workflow that creates an anchor point named *Edges* twice, and the second click says
    *An anchor point named "Edges" already exists.*

## Setting

These Steps change the Current layer.

### Blend mode

Sets the layer's blend mode, such as Multiply or Overlay.

### Opacity

Sets the layer's opacity, separately for each channel you tick.

### Fill content

Changes an **existing** layer instead of creating a new one:

- switches channels **On** or **Off** (on a Fill or Paint layer);
- sets a Fill layer's content: one material, or per channel a value, resource or
  anchor point.

Content needs a Fill layer. If the Current layer is another kind, the Workflow does not
start and the message ends in *needs a Fill layer.*

## At the end

These Steps always run after all layer Steps.

| Step | What it does |
|---|---|
| **Brush** | Makes a brush the active brush. Needs a Paint layer or a mask to be selected at that point, so add a mask before it on a Fill layer |
| **Menu command** | Runs a Painter menu command. Type its internal name, or use **Choose from list…** |
| **Save** | Saves the project |
