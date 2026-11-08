# Menu buttons

A Menu button runs one of Painter's own menu commands, for example **File → Save** or
**Window → Views → Log**.

## Add a Menu button

Click the **+** of a Group, then **Menu button**. A box at the top of the Panel says
*Click a command in Painter's menu to add it to "…". Esc cancels.* Then choose one way:

=== "Click the command"

    1. In Painter's main menu, click the command, including commands in submenus.
    2. The command runs as usual, and a new tile appears at the end of the Group.

=== "Choose from list…"

    1. In the box, click **Choose from list…**.
    2. Type in the search field to filter the list. Each row shows the command and the
       menu it is in, for example *Log — Window › Views*.
    3. Select a row and click **Add**, or double-click the row.

The tile shows the command's icon, or a purple menu symbol if the command has none. Its
name is the command's name.

!!! note "Square brackets in the list"
    Some rows end with a name in square brackets, for example *Save — File [SAVE_PROJECT]*.
    That is Painter's internal name for the command. You can ignore it.

### Cancel

Click **Cancel** in the box, or press ++esc++. If a Painter menu is open, the first
++esc++ closes the menu and the second one cancels.

## Use a Menu button

Click the tile. It does the same as clicking the command in Painter's menu.

If the command is greyed out in Painter at the moment, for example **Save** with no
project open, the Panel shows a message instead.

## Limits

- Only commands that are in one of Painter's menus can become a Menu button. Buttons
  inside other windows, such as the Layers window, cannot. The Panel then says *"…"
  cannot be a Menu button: Painter gives it nothing to find it by.*
- Some commands have no internal name, and Shelf+ finds them by their menu text. These
  Buttons stop working if you switch Painter to another language.
- If a command does not exist in your Painter version, the tile gets a
  [warning triangle](panel.md#warning-triangles) once a project is open.
