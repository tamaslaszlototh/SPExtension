# Glossary

**Panel**: The user's own window inside Substance 3D Painter. It can float or be docked. In v1 there is exactly one Panel. The product that provides it is called **Shelf+**.
_Avoid_: shelf (on its own, "shelf" means Painter's Assets window)

**Assets window**: Painter's own window listing brushes, materials, smart masks and other resources; older Painter versions and its internal names call it the "shelf". Brush buttons are created by dragging from it.
_Avoid_: shelf

**Button**: A single clickable item on the Panel. Every Button is exactly one of the following kinds: Brush button, Workflow button, or Menu button.

**Brush button**: A Button that makes a chosen brush preset the active brush in Painter.

**Workflow**: A user-defined, ordered sequence of Steps that Painter carries out one after another (e.g. "create Fill layer → add black mask"). The user creates it on the Panel. If a Step fails, the Workflow stops.
_Avoid_: process, macro

**Step**: A single action inside a Workflow, chosen from a fixed list of supported actions: layer and mask operations, effects, layer settings, picking an existing layer by its name, and (only at the end of a Workflow) brush selection, menu commands and saving. A Brush button or Menu button behaves like a Workflow with exactly one Step.

**Recording**: Creating a Workflow by performing its Steps in Painter while the Panel watches, then stopping. The captured Steps can be reviewed and corrected before the Workflow is saved.
_Avoid_: macro recording

**Current layer**: The layer a Step acts on while a Workflow runs. It starts as the layer selected when the Workflow is started, and changes only when a Step creates a new layer or picks an existing layer by its name. A Step cannot act on any other layer.

**Workflow button**: A Button that runs a Workflow.

**Menu button**: A Button that triggers an existing Painter menu command (e.g. Save).
_Avoid_: menu item (this means the original item inside Painter's menu, not the Button)

**Group**: A named, collapsible section of the Panel that holds an ordered set of Buttons. The user creates, renames and reorders Groups on the Panel; a Button belongs to exactly one Group.
_Avoid_: category, folder (a folder is a Painter layer type)

**Layout**: The Groups on the Panel, their order, and the Buttons inside each of them in order. In v1 there is exactly one Layout.
