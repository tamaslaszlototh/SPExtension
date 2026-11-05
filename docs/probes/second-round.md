# Second measurement round – findings

Status: **done.** All runs were on the home machine (Painter 11.1.0, Python 3.11, Qt / PySide 6.5.8). The company machine (12.2.0) was not measured in this round; its checks move to the first build.

| Run | Probes | What it measured |
|---|---|---|
| 1st run | pen probe, Recording probe (S11 only), Brush probe v3.7, Assets probe v1.0 | A, C; B and D failed (see below) |
| 2nd run | Assets probe v1.1 (`task/second-round` branch) | B, D, and what makes widget references go stale |

## A. Pen hover

- Painter does **not** disable mouse synthesis: `AA_SynthesizeMouseForUnhandledTabletEvents=True`. With a hovering pen, our buttons still get `Enter`, `HoverEnter`, `HoverMove`, `MouseMove` and `TabletMove`.
- Qt's own `setToolTip` (variant A) does **not** show with the pen. A custom tooltip works in all three variants: B (`tabletEvent`), C (event filter) and D (`QCursor.pos()` polling).
- Painter's own icons show no tooltip with the pen either.
- The `:hover` highlight probably works, because `Enter`/`HoverEnter` arrive with the pen. This is confirmed by the events only, not visually.

## B. `.abr` brush

- Dropping an `.abr` brush onto the panel works. Its URL is `resource://starter_assets/Kyle Brush Presets/Archive Inker_24?version=….abr`, with `type=BRUSH`, `usages=[BRUSH]`, `gui_name='Archive Inker'`.
- The icon:
  - The Assets tile's tooltip has an embedded **256×256 PNG**, which is sharp.
  - The tile's `DecorationRole` is 70×70.
  - The built-in `Basic Hard Pressure` (`type=PRESET`) behaves the same.
  - This confirms the icon order from the brush-icon prototype on 11.1 as well.
- A Qt-event click (`sendEvent` press and release on the view's viewport) **activates** the `.abr` brush on 11.1.

## C. Layer opacity (re-test of Recording S11)

- During ~4 s of dragging the opacity in the layer's row there were 168 `LayerStacksModelDataChanged` events and 39 diffs, each `CHANGED 'Layer 3'.opacity`.
- History got **one** row on release: `set blending opacity`. The History row closes the Step, and the diffs in between are merged.
- Only **one channel** changed (`BaseColor`). The other channels stayed at 1.0, so the opacity Step must store the channel.
- The user dragged back to 1.0, so the net change was 0. The recorder must drop a Step with no net change.

## D. Opening the Assets window

The probe set up each state itself, ran each method without clicking, and measured when the brush tile became clickable (visible and stable in the view).

| State | M4 `show_in_ui()` only | M1 `show()` + `raise_()` | M2 toggle action | M3 Window → Views → Assets |
|---|---|---|---|---|
| S1 open, visible | ✅ 63 ms | ✅ 62 ms | | |
| S2 behind another tab | ❌ (in the model, not visible) | ✅ 89 ms, switches tab | | |
| S3 closed | ❌ | ✅ 87 ms | ✅ 90 ms | ✅ 109 ms |
| S4 floating, then closed | ❌ | ✅ 125 ms, opens floating | | |

- `show_in_ui()` does **not** open a closed or hidden Assets window, and it does not switch tabs.
- `show()` + `raise_()` works in every state. The tile becomes clickable within ~60–125 ms.
- Real test: Assets closed → `show()` + `raise_()` → poll → Qt click. The brush became active.
- After S2 the Assets tab stays in front. The probe's `restoreState()` did not restore the active tab. This is a probe issue; the plugin does not restore the layout anyway.
- The M3 menu action is the same object as `dock.toggleViewAction()`.

## Stale widget references on 11.1 ("Internal C++ object … already deleted")

In the 1st run, almost every probe call failed with this error. The Assets probe v1.1 tested the cause right after startup:

| Step | View wrapper valid after? |
|---|---|
| T1 drop the result of `sp_ui.get_main_window()` | yes |
| T2 drop the **dock** wrapper (the view was found through `parentWidget()` walks up to the dock) | **no** |
| T3 drop an `allWidgets()` list | yes |
| T4 drop the results of `d.window()` / `d.parentWidget()` | **no** (the dock too) |
| T5 drop `tabifiedDockWidgets()` and a main window found through `allWidgets()` | yes |
| T6 drop the model wrapper | yes |
| T7 keep all wrappers, 1 s of event processing | yes |

- On 11.1, when the Python wrapper of an **ancestor** widget is dropped, the wrappers of its descendants become invalid. This happens to ancestors reached through `parentWidget()` / `window()`. The C++ widgets stay alive.
- With every wrapper kept alive for the plugin's lifetime, every call in the 2nd run worked.
- This also explains the earlier brush-button result "on 11.1 only the Windows mouse click works": the Qt-event path hit stale wrappers.
- Not measured on 12.2.0.

The 1st run's Assets probe v1.0 also had its own bug. Its `Run` object was garbage-collected, so its poll never ran. v1.1 keeps the `Run` objects alive.
