# Probe: dragging a Smart material button onto the Layers window

Status: **pending.** Runs as check F of [the v1.1.0-alpha.1 checklist](../testing/smart-material-buttons.md) on Painter 11.1.0 (home) and 12.2.0 (work).

## The question

Does Painter's Layers window accept a `QDrag` started by Shelf+ that carries the smart material's `text/uri-list`, and put the smart material where its own drop indicator shows?

## What the build sends

- `application/x-shelfplus-button` (so a drop inside the Panel stays a move or a delete);
- `text/uri-list`: the Button's version-less `resource://` URL, percent-encoded as in the Assets window's drag, with a trailing CRLF;
- supported actions Move and Copy (Move by default, for drops inside the Panel).

The Assets window's own drag may carry more formats. If the probe fails, the next thing to measure is which formats the Assets window's drag carries (an application event filter logging `mimeData().formats()` on a `Drop` onto the Layers window).

## Decision (from issue #47)

- **Works on both versions:** dragging stays; v1.1.0 is released as latest.
- **Works on only one version:** dragging is removed as below. The feature does not depend on the Painter version.
- **Does not work:** the drag part is removed entirely: no fallback that computes the drop position, no follow-up issue. `App.drag_uri_list` and its use in `QtPanelView.start_drag` go, and the drag sentence goes from the `GLOSSARY.md` definition and the manual. Clicking is then the whole feature.

## Results

| Version | Drop line shown | Lands at the line | Panel drops unchanged | Recorded (check C, step 4) | Notes |
|---|---|---|---|---|---|
| 11.1.0 | | | | | |
| 12.2.0 | | | | | |
