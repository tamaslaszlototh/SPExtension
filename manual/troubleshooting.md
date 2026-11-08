# Troubleshooting & FAQ

## The Panel is not visible

- Open it from **Window → Views → Shelf+**.
- If it is not in that menu, check that **ShelfPlus** is enabled in Painter's **Python**
  menu.
- Check that the `ShelfPlus` folder is directly inside
  `Documents\Adobe\Adobe Substance 3D Painter\python\plugins`, not in a subfolder such as
  `ShelfPlus-v1.0.0\ShelfPlus`.

## A tile has a yellow warning triangle

The Button needs something that is not available here:

| Hover text | Why | What to do |
|---|---|---|
| *(not available on this machine)* on a Brush button | The brush was renamed, deleted, or exists only on another machine | Drag the brush in again, then delete the old tile |
| *(not available in this Painter version)* on a Menu button | The command does not exist in this Painter version, or Painter's language changed | Add the command again, or switch Painter back to English |

Workflow buttons do not get a triangle. If a resource a Workflow uses is missing, clicking
it says so and the Workflow [does not start](#a-workflow-did-not-start).

## Clicking a Brush button does not change the brush

- Painter changes the brush only while a Paint layer or a mask is selected. Select one
  first.
- If the Panel says *"…" did not appear in the Assets window within … seconds*, Painter
  was busy. Try again.

## A Menu button says the command "is not available yet"

Painter may still be building its menus, or the command needs an open project. Open a
project and wait a few seconds.

## A Workflow did not start

The message on the Panel says which Step stopped it. Nothing in your project was changed.

| Message | What to do |
|---|---|
| *open a project first* | Open a project |
| *needs a selected layer* | The first Steps act on the selected layer. Select a layer in the Layers window |
| *The Current layer has no mask. Add a mask before this Step.* | Add a Mask Step before the effect on mask |
| *needs a Paint layer or a mask* | Add a Mask Step before the Brush Step, or start from a Paint layer |
| *needs a Fill layer.* / *needs a Fill or Paint layer.* | A [Fill content](steps.md#fill-content) Step is acting on the wrong kind of layer |
| *uses the … channel, which this texture set does not have* | Untick that channel in the editor, or use another texture set |
| *This resource is not available on this machine: …* | Choose the resource again in the editor |
| *An anchor point named "…" already exists.* | Rename or delete the existing anchor point, or change the name in the Step |
| *No anchor point named "…".* / *Several anchor points named "…".* | A Step refers to an anchor point by name. There must be exactly one with that name |
| *must come before the brush, menu and save Steps* | Open the Workflow in the editor and save it again. The editor fixes the order |

## Recording does not start

- *Open a project first: Recording watches its layer stack.* Open a project.
- *Shelf+ is already recording.* Click **Stop** in the REC bar first.

## Something I did was not recorded

See [What is not recorded](recording.md#what-is-not-recorded). Add the missing Steps in the
editor after **Stop**.

## The Panel says the Layout was saved by a newer Shelf+

You are running an older Shelf+ than the one that last saved your Buttons, for example
after copying `%APPDATA%\ShelfPlus` from another machine. Your Buttons work, but you
cannot change them. [Update Shelf+](updates.md) to edit them again.

## My Buttons are gone

Shelf+ keeps backups in `%APPDATA%\ShelfPlus\`:

- `layout.json` is your current Layout.
- `layout.bak.json` is the one before the last change.
- If `layout.json` could not be read, Shelf+ sets it aside as
  `layout.broken-<date>-<time>.json` and loads the backup.

To restore a backup, close Painter, copy the backup over `layout.json`, and start Painter
again.

## How do I go back to the default Buttons?

Close Painter, delete `layout.json` in `%APPDATA%\ShelfPlus\`, and start Painter again.
This removes all your own Buttons.

## Can I use my Buttons on another computer?

Yes. Copy `layout.json` from `%APPDATA%\ShelfPlus\` on one computer to the same folder on
the other, with Painter closed. Brushes and resources that the other computer does not
have will show a warning triangle.

## Still stuck?

[Report the problem](updates.md#report-a-problem) with **☰ → Copy diagnostics**.
