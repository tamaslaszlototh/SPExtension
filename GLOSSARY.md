# Glossary

**Panel**: The user's own window inside Substance 3D Painter. It can float or be docked. In v1 there is exactly one Panel.

**Button**: A single clickable item on the Panel. Every Button is exactly one of the following kinds: Brush button, Workflow button, or Menu button.

**Brush button**: A Button that makes a chosen brush preset the active brush in Painter.

**Workflow**: A user-defined, ordered sequence of Steps that Painter carries out one after another (e.g. "create Fill layer → add black mask"). The user creates it on the Panel. If a Step fails, the Workflow stops.
_Avoid_: process, macro

**Step**: A single action inside a Workflow. It can be anything a Button can do (menu command, brush selection), as well as other Painter actions, such as layer and mask operations.

**Workflow button**: A Button that runs a Workflow.

**Menu button**: A Button that triggers an existing Painter menu command (e.g. Save).
_Avoid_: menu item (this means the original item inside Painter's menu, not the Button)

**Layout**: The set of Buttons on the Panel and their order. In v1 there is exactly one Layout.
