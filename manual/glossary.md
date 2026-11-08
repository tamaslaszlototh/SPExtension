# Glossary

**Panel**
:   The Shelf+ window inside Substance 3D Painter. It can float or be docked. There is one
    Panel.

**Assets window**
:   Painter's own window that lists brushes, materials, smart masks and other resources.
    Older Painter versions call it the "shelf". You create Brush buttons by dragging from
    it.

**Group**
:   A named section of the Panel that holds Buttons in order. You can collapse it. Each
    Button belongs to exactly one Group.

**Layout**
:   All your Groups, their order, and the Buttons in each of them. It is saved in
    `%APPDATA%\ShelfPlus\layout.json`.

**Button**
:   One clickable tile on the Panel. Every Button is a Brush button, a Menu button or a
    Workflow button.

**Brush button**
:   A Button that makes a chosen brush or tool preset the active brush.

**Menu button**
:   A Button that runs one of Painter's existing menu commands, such as **File → Save**.

**Workflow**
:   An ordered list of Steps that Painter carries out one after another, for example
    *Fill layer → Black mask*. If a Step cannot run, the Workflow does not start.

**Workflow button**
:   A Button that runs a Workflow.

**Step**
:   One action inside a Workflow, chosen from a fixed list. See the
    [Step reference](steps.md).

**Current layer**
:   The layer a Step acts on while a Workflow runs. It starts as the layer selected when
    you click the Button, and changes only when a Step creates a layer or picks one by
    name.

**Recording**
:   Creating a Workflow by doing its Steps in Painter while the Panel watches. You check
    and correct the Steps before saving.
