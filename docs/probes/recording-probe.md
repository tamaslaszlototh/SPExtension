# Recording probe – findings

Status: **both runs analysed.** A few steps are still inconclusive (see below).

| Run | Painter | Python | Qt / PySide |
|---|---|---|---|
| Home machine | 11.1.0 | 3.11.6 | 6.5.8 / 6.5.8 |
| Company machine | 12.2.0 | 3.13.9 | 6.8.7 / 6.8.7 |

The probe (SPX Recording Probe v1.0, same version on both machines) walked the user through scripted steps (S00–S30) while listening to:
- `substance_painter.event` events
- a layer-stack snapshot diff (on event and by polling)
- `QAction.triggered` and `QMenu.triggered` hooks
- dock title changes
- a key event filter
- drops onto the probe panel
- the History dock's `QUndoView`

Because the two machines run different Painter versions, a difference between the runs may be a version difference, not a machine difference.

## Same on both versions

- **Layer stack diff after `LayerStacksModelDataChanged`** caught every layer-stack change: add Fill / Paint layer / Folder, black mask, Levels, Anchor point, blend mode, rename, delete, reorder.
  - Callback runs on the GUI thread.
  - Usually **2 events per operation**, so debounce them into one diff.
  - Snapshot cost: 10–17 ms at ~35 nodes (11.1.0, home); 28–45 ms at 11–26 nodes (12.2.0, company). 12.2.0 exposes more channels per layer (e.g. `Opacity`, `EmissionColor`). Still fine for a debounced diff, but it should not run on every poll tick.
- **Texture set switch** (12.2.0; skipped on 11.1.0): fires `LayerStacksModelDataChanged`; the active stack changes (e.g. `coat/` → `boots/`). The recorder must notice it and not diff two different stacks against each other.
- **uids are stable across undo/redo**: a redone layer comes back with the same uid. Layers can be referenced by uid during a Recording.
- **History (`QUndoView`) is the most reliable signal.**
  - Every committed operation adds a row with a label (`Add fill layer`, `set blending mode`, `label`, `Move layer(s)`, `Set generator`, `Set effect`, `Drop layer preset`, `Add stroke`, …). The common labels are identical on both versions.
  - Undo and redo keep the row count and only move the current index. This is the only way to tell an undo from a delete: the diff shows `REMOVED` for both.
  - Works whether undo comes from Ctrl+Z, the Edit menu or a click in the History panel.
  - Readable even while the History dock is hidden.
  - The dock title differs between versions (`History - Painting Mode` vs `History`), but `objectName='history'` is the same.
- **`QAction.triggered` hooks** fired for: Add fill layer, Add layer, Add group, Add black mask, Add generator / filter / levels / anchor point, Remove layer(s), Save (menu and Ctrl+S), Close, tool switches (Eraser, Projection, Paint).
  - Layer-stack actions have an **empty `objectName`**, so they can only be identified by their text, which is locale-dependent.
  - Action text can be multi-line (`'Add fill layer\n\nHold Alt to enable all channels'`); use the first line.
- **Smart material drop**: the whole group arrives in a single diff, and the group name matches the dropped resource name.
- **Project close**: `ProjectEditionLeft`, `BusyStatusChanged` and `ProjectAboutToClose` arrive as expected.

### Anchor point sources (v0.8.3-rc.1 diagnostics, 11.1.0 only so far)

- A Fill channel whose source is an anchor point (Properties → channel → *Anchor points* tab) has `get_source(channel)` returning a **`source.SourceReference`**. Public members: `alpha_matte`, `anchor`, `channel_mapping`, `get_levels`, `referenced_channel`, `set_levels`, `uid`.
- `SourceReference.anchor` is the `AnchorPointEffectNode`, and its `get_name()` gives the anchor's name.
- The anchor point in that run read as `Fill layer 2`: probably Painter names an anchor point added from the UI after its layer (not confirmed). Recording stores whatever name it reads.
- `referenced_channel` and `channel_mapping` are not recorded; replay leaves them at Painter's default. From v0.8.4 the first anchor source read logs both, to learn what they hold.
- Still to check: the same on 12.2.0.

## Differences between the versions

| Topic | 11.1.0 (home) | 12.2.0 (company) |
|---|---|---|
| `QMenu.triggered` hook | never fired | fires: main menu (`File/Save`, `Edit/Undo…`, `Edit/Redo`, `Views/Log`), context menus (`Add black mask`, `Add generator`, …), blend mode popup (`Multiply`) |
| Dock title hook (`Tool` dock) | no changes logged | follows the selection (`Properties - Fill`, `Properties - Generator`, …) |
| Submenu command (S27) | nothing captured | captured via `QMenu` |
| Undo/redo from Edit menu | no signal except History | `QMenu` fires too |
| Smart mask History label | `Drop resource on new mask` (layer had no mask) | `Drop resource` (layer already had a mask) |

The smart mask label difference may come from the situation, not the version: on 11.1.0 the mask was created by the drop, on 12.2.0 it went into an existing mask.

## Problems (on both versions unless noted)

1. **A generator's or filter's source changes without any event.** The renamed node (`Generator (empty)` → `Dirt`) and its new `source` showed up only through polling. The diff needs another trigger, for example the History row `Set generator` / `Set effect`.
2. **Brush preset change and brush settings (e.g. brush opacity) are invisible on both versions**: no action, no menu, no event, no History row. Not recordable this way.
3. **Smart mask**: the diff only shows a `Mask Editor` generator (plus a `has_mask`/`mask_bg` change if the layer had no mask). Its name does not match the dropped resource (`Cavity Rust`, `Dirt`). The resource can only be identified from the drop data. The probe's resource `usage` lookup on drop raised `AttributeError` on both versions; this needs fixing.
4. **Undo/redo triggers no `QAction`.** Ctrl+Z / Ctrl+Y only log the modifier (`Ctrl+Control`), not Z/Y. On 12.2.0 the Edit menu label was stale (`Undo Add stroke` while the last operation was `Add fill layer`), so do not trust its text. Detect undo/redo from the History current index.
5. **Duplicate hook calls**:
   - Tool actions fire twice per switch.
   - On 12.2.0, one main-menu click is reported twice: `Views/Log` + `Window/Log`, `Views/History` + `Window/History`.
   - On 12.2.0, `Save` is reported as both an action and a menu item.

   Deduplicate by action identity and timestamp.
6. **The key filter also captures typing in text fields**, including the probe's own note field. The target is always `QWidgetWindow`, so a focus-widget check is needed.
7. **Snapshot during save fails** with `ProjectError('The project is locked.')`. Seen once on 11.1.0 and 3 times on 12.2.0. The recorder must tolerate it and retry.
8. **Painting** shows only as `Add stroke` History rows and `TextureStateEvent`s, not in the diff. That is fine, because strokes are not Steps; the recorder must not mistake them for an unknown Step.

## Inconclusive (to re-check)

- **S11 Opacity drag**: the user dragged the **brush** opacity slider (a tool setting), not a layer's opacity. No diff and no History row on either version: like the brush preset (problem 2), brush settings are invisible to every hook. **Layer opacity has not been tested yet**; it needs a re-test.
- **S25 Save from menu on 11.1.0** reported `Save as...`. On 12.2.0 it reported `Save` correctly, so on 11.1.0 Save as was most likely chosen by hand.

## Recorder design (based on both runs)

- **Primary trigger**: History.
  - New row = one operation.
  - Current index goes down = undo.
  - Current index goes up without a new row = redo.
- On every trigger, run a layer-stack diff. `LayerStacksModelDataChanged` only makes it faster. Track the active stack, so that a texture set switch is not read as a change.
- **Naming the operation**:
  - The `QAction` hook (first line of the text) and the drop hook give the operation's name. The `QMenu` hook is an extra source on 12.2.0 only.
  - The History label is the fallback when no hook fires (blend mode, rename, reorder).
  - The diff provides the content and the target layer.
- Brush selection and brush settings cannot be recorded. They have to be added by hand when the Recording is reviewed.
