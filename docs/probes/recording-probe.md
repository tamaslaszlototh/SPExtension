# Recording probe – findings

Status: **partial** — home machine run analysed; company machine run still pending. Conclusions below are provisional until both runs are compared.

| Run | Painter | Python | Qt / PySide | Status |
|---|---|---|---|---|
| Home machine | 11.1.0 | 3.11.6 | 6.5.8 / 6.5.8 | done |
| Company machine | ? | ? | ? | pending |

The probe (SPX Recording Probe v1.0) walked the user through scripted steps (S00–S30) while listening to: `substance_painter.event` events, a layer-stack snapshot diff (on event + polling), `QAction.triggered` hooks, a key event filter, drops onto the probe panel, and the History dock's `QUndoView`.

## What works

- **Layer stack diff after `LayerStacksModelDataChanged`** caught every layer-stack change: add Fill / Paint layer / Folder, black mask, Levels, Anchor point, blend mode, rename, delete, reorder.
  - Callback runs on the GUI thread.
  - Snapshot cost ~10–17 ms at ~35 nodes.
  - Usually **2 events per operation** → debounce into one diff.
- **uids are stable across undo/redo**: a redone layer comes back with the same uid. Layers can be referenced by uid during a Recording.
- **History (`QUndoView`) is the most reliable signal.** Every committed operation adds a row with a label (`Add fill layer`, `set blending mode`, `label`, `Move layer(s)`, `Set generator`, `Drop layer preset`, `Drop resource on new mask`, `Add stroke`, …). Undo/redo keep the row count and only move the current index — this is the only way to tell undo apart from a delete (the diff shows `REMOVED` in both cases).
- **`QAction.triggered` hooks** fired for: Add fill layer, Add layer, Add group, Add black mask, Add generator / filter / levels / anchor point, Remove layer(s), Save (also via Ctrl+S), Close, tool switches (Eraser, Projection, Paint).
  - Layer-stack actions have an **empty `objectName`** → identifiable only by text (locale-dependent).
  - Action text can be multi-line (`'Add fill layer\n\nHold Alt to enable all channels'`) → use the first line.
- **Smart material drop**: the whole group arrives in a single diff; the group name matches the dropped resource name.
- **Project close**: `ProjectEditionLeft`, `BusyStatusChanged`, `ProjectAboutToClose` arrive as expected.

## Problems

1. **Generator / filter source change emits no `LayerStacksModelDataChanged`.** The name change (`Generator (empty)` → `Dirt`) and `source` change were only seen by polling. Needs another trigger (e.g. the History row `Set generator` / `Set effect`).
2. **Brush preset change is invisible**: no action, no event, no History row. Currently not recordable.
3. **Smart mask**: the diff only shows a `Mask Editor` generator + `has_mask`/`mask_bg` change; the name does not match the dropped resource (`Cavity Rust`). Identifiable only from the drop data or the History row `Drop resource on new mask`. The probe's resource `usage` lookup on drop raised `AttributeError` — to fix.
4. **Undo/redo via Edit menu or History click fires no `QAction`.** Ctrl+Z / Ctrl+Y only showed the modifier key (`Ctrl+Control`), not Z/Y. Must be detected from the History current index.
5. **Key filter also captures typing in text fields** (incl. the probe's own note field); target is always `QWidgetWindow`. Needs a focus-widget check.
6. **Tool actions fire twice** per switch → deduplicate.
7. **Snapshot during save fails** with `ProjectError('The project is locked.')` → the recorder must tolerate and retry.
8. **Painting** shows only as `Add stroke` History rows and `TextureStateEvent`s, not in the diff. Fine — strokes are not Steps.

## Inconclusive (to re-check)

- **S11 Opacity drag**: no diff and no History row — probably the change was not committed.
- **S25 Save from menu**: `Save as...` action fired — unclear whether the user picked Save as or Save opened Save as.
- **S27 Submenu command**: nothing captured.
- **S24 Texture set switch**: skipped.

## Provisional recorder design

- **Primary trigger**: History — new row = one operation, decreasing current index = undo, increasing without a new row = redo.
- On every trigger run a layer-stack diff; `LayerStacksModelDataChanged` only speeds it up.
- `QAction` / drop hooks provide the operation's **name**; the diff provides its **content and target layer**.

## Open questions for the company machine run

- Same History labels and action texts (locale)?
- Same event counts and missing events (problems 1, 4)?
- Does the brush change stay invisible?
