# Testing Brush buttons (Shelf+ v0.3.2-rc.1)

This build adds **Brush buttons**. Drag a brush from the Assets window onto the Panel, and from then on one click on its tile makes it the active brush.

Please run the checks once on **each machine**:

- **Home:** Painter 11.1.0
- **Work:** Painter 12.2.0, no admin rights. On this machine, these checks are also the first real test of opening the Assets window and clicking a brush in it.

One run takes about 20 minutes. Write the results in the [table at the end](#results).

**What is expected not to work yet:**

- Clicking a Workflow button (for example *Save*) does nothing.
- In the **+** menu, *Menu button* and *Workflow button* say *(coming soon)* and are greyed out. *Brush button* only tells you to drag a brush in.

Neither of these is a failure.

## 1. Install the build

1. Close Painter.
2. Download **ShelfPlus-v0.3.2-rc.1.zip** from the [v0.3.2-rc.1 release page](https://github.com/tamaslaszlototh/ShelfPlus/releases/tag/v0.3.2-rc.1).
3. Open `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`. If there is a `ShelfPlus` folder there already, delete it.
4. Copy the `ShelfPlus` folder from the zip into that `plugins` folder.
5. Start Painter and open a project (any project with a mesh you can paint on).
6. In the Panel's top right corner, click **☰**. The first line must say **Shelf+ v0.3.2**.
   - If it says an older version, or Painter showed "Shelf+ v0.3.2 failed to start; reverted to …", stop here.
   - Click **☰ → Copy diagnostics** and send what it copies.

## 2. The checks

### A. Dragging brushes onto the Panel

Open the Assets window (**Window → Views → Assets**) and find these three brushes. The search field of the Assets window helps.

| Kind | Example |
|---|---|
| A built-in tool preset | *Basic Hard* |
| A preset you saved yourself | any of yours (save one first if you have none) |
| An `.abr` brush | *Archive Inker* (from *Kyle Brush Presets*) |

1. Drag each one from the Assets window onto a Group of the Panel. Drop it between two tiles, or on the Group's name.
   - ✅ A new tile appears where you dropped it, with the brush's picture.
   - ✅ Hover over the tile: its name is the brush's name.
   - ✅ The picture is **sharp**, like the big picture Painter shows when you hover over the brush in the Assets window.
2. Drag something that is **not** a brush (for example a material) onto a Group.
   - ✅ No tile is added. The Panel says it is not a brush or tool preset.

### B. Clicking a Brush button

Do this for **each** of the three Brush buttons, in each of the four Assets window states below. Before each click, pick a different brush by hand in Painter, so you can see the change.

| State | How to set it up |
|---|---|
| **Open** | The Assets window is visible. |
| **Closed** | Close the Assets window with its **×**. |
| **Behind a tab** | Dock the Assets window as a tab next to another window (for example Layers), then click the other tab so Assets is hidden behind it. |
| **Floating** | Drag the Assets window out so it floats, then close it with its **×**. |

1. Click the tile on the Panel.
   - ✅ The Assets window ends up open and in front (in the floating case, floating again).
   - ✅ Within about a second, the brush is the active brush: check the tool's properties, or paint a stroke.
   - ✅ The Assets window stays open afterwards.
2. If a click did nothing for a few seconds, the Panel shows a message under its top bar. Write that message in the notes.
3. If you have two brushes with the **same name** (for example your own copy of *Basic Hard*), drag one in and click it. Write in the notes whether the right one became active and got the right picture: Shelf+ finds the tile by its name.

### C. After a restart

1. Restart Painter. Watch the Panel while Painter starts up.
   - ✅ No Brush button shows the yellow warning triangle, not even for a moment.
2. Open a project again.
3. Click each Brush button once, with the Assets window closed.
   - ✅ Each one still works, as in check B.

### D. A missing brush

1. Close Painter.
2. Open the folder `%APPDATA%\ShelfPlus`: paste that path into the File Explorer address bar.
3. Open `layout.json` in Notepad. Find one Brush button: it has `"kind": "brush"` and a `"resource"` line, for example
   `"resource": "resource://starter_assets/Basic Hard",`
4. Add `XYZ` to the end of the name inside the quotes, so it reads `"resource://starter_assets/Basic Hard XYZ",`. Save the file.
5. Start Painter.
   - ✅ Once Painter has finished loading its brushes (this can take up to half a minute after start-up), that tile has a small yellow warning triangle in its corner. Hovering over it says *(not available on this machine)*.
   - ✅ Clicking it only shows a message: *This brush is not available on this machine: …*. The active brush does not change.
   - ✅ The other Brush buttons still work.
6. To clean up, delete that tile: drag it onto **Delete**.
   - ✅ While the tile is over **Delete**, it lights up with an orange border, like a Group you drop a tile on.

### E. Smaller pictures (Home, 11.1 only)

On the home machine, some brushes may not have a big picture and get a smaller or blurry one, or a plain blue brush symbol.

1. Drag in a few more brushes of different kinds (built-in, your own, `.abr`).
2. Write in the notes which ones got a **blurry** picture or the **blue brush symbol**.
3. Click **☰ → Copy diagnostics** and send it along: the log says where each picture came from.

## Results

Fill in **Pass**, or **Fail** with a short note on what happened. Write anything odd in **Notes**, even if the check passed, for example flicker, slowness, or a Painter warning.

| Check | Home (11.1.0) | Work (12.2.0) | Notes |
|---|---|---|---|
| 1. Install: ☰ shows v0.3.2 | | | |
| A. Drag brushes in, sharp pictures | | | |
| B. Click: Assets open | | | |
| B. Click: Assets closed | | | |
| B. Click: Assets behind a tab | | | |
| B. Click: Assets floating | | | |
| C. After a restart | | | |
| D. A missing brush | | | |
| E. Brushes with a smaller picture | | — | |

**If something fails:**

1. Click **☰ → Copy diagnostics** right away, before restarting Painter.
2. Paste what it copies into your message. It contains the versions and the recent log.

Send the filled-in table back, for example as a comment on [issue #26](https://github.com/tamaslaszlototh/ShelfPlus/issues/26).
