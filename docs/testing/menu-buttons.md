# Testing Menu buttons (Shelf+ v0.4.1-rc.1)

This build adds **Menu buttons**. A Menu button runs one of Painter's own menu commands (for example *File → Save*) with one click on its tile.

You can add one in two ways:

- **Capture:** click **+ → Menu button** on the Panel, then click the command in Painter's menu. That command becomes the Button.
- **From a list:** while the Panel is waiting for a command, click **Choose from list…** and search for the command.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights

One run takes about 15 minutes. Write the results in the [table at the end](#results).

**What is expected not to work yet:**

- Clicking a Workflow button (for example *Save* in the *General* Group) does nothing.
- In the **+** menu, *Workflow button* says *(coming soon)* and is greyed out.
- Commands that are not in any of Painter's menus (for example the buttons of the Layers window) cannot become a Menu button. The box at the top of the Panel then says *"… cannot be a Menu button: it is in none of Painter's menus."* Write down which commands you tried, but this does not count as a failure.
- If you rename or move a Painter menu command by changing Painter's language, Buttons for commands that have no internal name stop working. Painter in English is fine.

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.4.1-rc.1.zip** from the [v0.4.1-rc.1 release page](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.4.1-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project.
6. In the Panel's top right corner, click **☰**. The first line must say **Shelf+ v0.4.1**.
   - If it says an older version, or Painter showed "Shelf+ v0.4.1 failed to start; reverted to …", stop here.
   - Click **☰ → Copy diagnostics** and send what it copies.

## 2. The checks

### A. Capture a command from Painter's menu

1. On the Panel, click the **+** of a Group, then **Menu button**.
   - ✅ A box appears at the top of the Panel: *"Click a command in Painter's menu to add it to “…”. Esc cancels."*, with **Choose from list…** and **Cancel**.
2. In Painter's main menu, click a command that opens a window, for example **Window → Views → Log**. (Avoid commands that change your project for now.)
   - ✅ The command runs as usual.
   - ✅ A new tile appears at the end of the Group, with the command's icon, or a purple menu symbol if the command has no icon of its own.
   - ✅ Hover over the tile: its name is the command's name.
   - ✅ The box at the top of the Panel is gone.
3. Do it again with a second command, for example **File → Save**.
4. **Work (12.2) only:** add a third command from a **submenu**, for example from **Window → Views** or another menu with a ▸ arrow.
   - ✅ The tile appears, as in step 2.

### B. Cancel

1. Click **+ → Menu button**, then click **Cancel** in the box.
   - ✅ The box disappears. Clicking a menu command now adds nothing.
2. Click **+ → Menu button** again. Click into Painter's 3D view, then press **Esc**.
   - ✅ The box disappears.
3. Click **+ → Menu button** again. Open Painter's **File** menu, then press **Esc** once to close the menu.
   - ✅ The menu closes, but the box stays. Press **Esc** again: now the box disappears.

### C. Add from the list

1. Click **+ → Menu button**, then **Choose from list…**.
   - ✅ A window opens with a long list of Painter's commands. Each row shows the command and the menu it is in, for example *Log — Window › Views*.
2. Type a few letters of a command's name into the search field, for example `export`.
   - ✅ Only matching commands stay in the list.
3. **Home (11.1):** pick a command that is inside a **submenu** (a menu with a ▸ arrow). On 11.1 this is the only way to add one. **Work (12.2):** pick any command.
4. Double-click it, or select it and click **Add**.
   - ✅ The window closes and the tile appears at the end of the Group.

### D. Running the Buttons

Click each of your three new tiles.

- ✅ Each one does the same as clicking the command in Painter's menu.
- ✅ Clicking a tile does **not** add another tile, even while the Panel is waiting for a command (click **+ → Menu button** first, then a tile, to try this).
- If a command is greyed out in Painter's menu at the moment (for example *Save* with no project open), the tile shows a message instead of doing nothing.

### E. After a restart

1. Restart Painter and open a project again.
2. Click each of the three tiles.
   - ✅ Each one still works, as in check D.
   - ✅ No tile shows the yellow warning triangle.

### F. A missing command

1. Close Painter.
2. Open the folder `%APPDATA%\ShelfPlus`: paste that path into the File Explorer address bar.
3. Open `layout.json` in Notepad. Find one Menu button: it has `"kind": "menu"` and an `"action"` line, for example
   `"action": "SAVE_PROJECT",`
4. Add `XYZ` to the end of the name inside the quotes, so it reads `"action": "SAVE_PROJECTXYZ",`. Save the file.
5. Start Painter.
   - ✅ That tile has a small yellow warning triangle in its corner. Hovering over it says *(not available in this Painter version)*.
   - ✅ Clicking it only shows a message: *This menu command is not available in this Painter version: …*. Nothing else happens.
6. To clean up, delete that tile: drag it onto **Delete**.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened. Write anything odd in **Notes**, even if the check passed, for example flicker, slowness, or a Painter warning.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.4.1 | | | |
| A. Capture from the menu | | | |
| A4. Capture from a submenu | — | | |
| B. Cancel (button, Esc, Esc in a menu) | | | |
| C. Add from the list | | | |
| D. Running the Buttons | | | |
| E. After a restart | | | |
| F. A missing command | | | |
| Commands that could not be added | | | |

**If something fails:**

1. Click **☰ → Copy diagnostics** right away, before restarting Painter.
2. Paste what it copies into your message. It contains the versions and the recent log.

Send the filled-in table back, for example as a comment on [issue #27](https://github.com/tamaslaszlototh/SPExtension/issues/27).
