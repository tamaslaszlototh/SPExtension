# Research: layer stack and mask operations, and undo grouping in the Painter Python API (11.1.0 vs 12.2.0)

Ticket: [#4](https://github.com/tamaslaszlototh/SPExtension/issues/4) · Map: [#1](https://github.com/tamaslaszlototh/SPExtension/issues/1) · Researched: 2026-11-03

## Question

Which layer stack operations can a plugin do through the Painter Python API on 11.1.0 and on 12.2.0? For example: creating fill or paint layers and folders, adding black or white masks, adding generators or filters, setting blend mode and opacity, and handling the selection. Can several operations be combined into **one undo step** (`ScopedModification`)? What happens when there is no active texture set or no layer is selected?

## Short answer

- The `substance_painter.layerstack` module exists since Painter 10.0 (API 0.3.0), so **both target versions have it**. Every operation the ticket lists is available on **both** 11.1.0 and 12.2.0 with the same API.
- `layerstack.ScopedModification(name)` is a context manager that combines every layer stack change inside the `with` block into **one history entry**, so one Ctrl+Z undoes all of it. Textures are recomputed once, when the block exits.
- **`set_selected_nodes` and `set_selection_type` raise `RuntimeError` when called inside a `ScopedModification`.** A Workflow that changes the selection cannot do so inside the undo group.
- Errors are exceptions: `ProjectError` (no project open), `RuntimeError` (no active stack), `ServiceNotFoundError` (services not started yet), and `ValueError` (invalid position, resource, node, or a missing or duplicate mask). Nothing fails silently.
- Version differences that matter for this plugin: **11.1.0 has a known bug** where editing the layer stack outside a scoped modification block gives an "unexpected error". It was fixed in 11.1.1. 12.x adds only smart material and smart mask export to disk and a new geometry mask API, and moves to Python 3.13 and Qt 6.8.6.

## Sources and how they were read

- Official Python API reference, now on Adobe Experience League (`experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/...`). The helpx.adobe.com copy named in the ticket answered HTTP 403 (Akamai "Access Denied") to automated fetching, so I read the Experience League copy of the same docs. The textureset `get_active_stack` exception list comes from the helpx page's search-engine index text (see the Uncertain section).
- Official Python API changelog and Painter release notes ("All Changes", "Version 10.0", "Version 12.2").
- Pages were read through a fetch tool that summarises pages. Signatures and exception texts below are the quoted parts. Code examples were written for this note, not copied.

There is **one online version** of the API reference (the latest). It does not mark which version added each item, so version coverage below comes from the **changelog** and the **release notes**.

## Version mapping (verified)

| Painter | Python API | Layer-stack-related changes | Source |
|---|---|---|---|
| 10.0.0 | 0.3.0 | `layerstack` module added. Includes "Allow to batch actions to have a single undo/redo" and "Allow to pause/unpause engine". | [Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog), [10.0 release notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/old-versions/version-10-0) |
| 10.0.1 | 0.3.1 | `set_selection_type()` fix for instance-parent properties. `set_source` raises `ValueError` on anchor-point cycles. | Changelog |
| 11.0.0 | 0.3.4 | `create_smart_material()`, `create_smart_mask()` (save to shelf) | Changelog |
| 11.0.3 | 0.3.4 | Fix: "Scoped Modification does not appear in History window" | [All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes) |
| **11.1.0** | **0.3.5** | `is_3d_projection_mode()`, fill `get/set_symmetry_parameters()` | Changelog |
| 11.1.1 | 0.3.5 | Fix: "**Unexpected error when editing layer stack outside of scoped modification block**" | All Changes |
| 12.0.0 | (no API bump listed) | Python updated to 3.13, Qt to 6.8.6 | All Changes |
| 12.0.2 | 0.3.6 | `export_as_smart_material()`, `export_as_smart_mask()`. Fix: "Unexpected error when adding a channel with scoped modification" | Changelog, All Changes |
| 12.1.0 | 0.3.7 | `LayerNode.get/set_geometry_mask()` and `GeometryMask*Params`. The old geometry-mask setters are deprecated. | Changelog |
| **12.2.0** | (no entry) | The 12.2 notes have **no** Python or scripting items. The changelog stops at 0.3.7. | [12.2 release notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/version-12-2), Changelog |

So for this plugin, **11.1.0 means API 0.3.5** and **12.2.0 means API 0.3.7** (the latter is an inference, because 12.2 has no changelog entry).

## Operations table

Legend: ✅ available · ⚠️ available but deprecated or with a known bug · ❌ not available through the API.

| Operation | API | 11.1.0 (0.3.5) | 12.2.0 (0.3.7) | Notes / errors |
|---|---|---|---|---|
| Get the active stack (texture set) | `textureset.get_active_stack()` | ✅ | ✅ | `ProjectError` (no project), `RuntimeError` (no active stack), `ServiceNotFoundError` |
| Set the active stack | `textureset.set_active_stack(stack)` | ✅ | ✅ | `ValueError` if the stack is invalid |
| List root layers | `layerstack.get_root_layer_nodes(stack)` | ✅ | ✅ | `ValueError` if the stack is invalid |
| Navigate (parent, siblings, children, effects) | `Node.get_parent/get_next_sibling/get_previous_sibling`, `GroupLayerNode.sub_layers()`, `LayerNode.content_effects()/mask_effects()` | ✅ | ✅ | |
| Look up a node by uid | `layerstack.get_node_by_uid(uid)` | ✅ | ✅ | `ValueError` if the uid is invalid |
| Choose where to insert | `InsertPosition.from_textureset_stack / above_node / below_node / inside_node(node, NodeStack.Substack/Content/Mask)` | ✅ | ✅ | Layers go next to layers or into a group's Substack. Effects go into Content/Mask or next to effects. |
| Paint layer or effect | `insert_paint(position)` | ✅ | ✅ | `ValueError` for an invalid position. Strokes are not accessible from Python. |
| Fill layer or effect | `insert_fill(position)` | ✅ | ✅ | `ValueError` for an invalid position |
| Folder (group) | `insert_group(position)` | ✅ | ✅ | Only at the stack top or above/below a layer |
| Instance layer | `instantiate(...)` | ✅ | ✅ | |
| Generator effect | `insert_generator_effect(position, generator_substance=None)` | ✅ | ✅ | `ValueError` for an invalid position, or a resource without `Usage.GENERATOR` |
| Filter effect | `insert_filter_effect(position, filter_substance=None)` | ✅ | ✅ | `ValueError` for an invalid position, or a resource without `Usage.FILTER` |
| Levels / Compare mask / Color selection / Anchor point | `insert_levels_effect`, `insert_compare_mask_effect`, `insert_color_selection_effect`, `insert_anchor_point_effect` | ✅ | ✅ | Compare mask and Color selection only inside Content/Mask |
| Smart material | `insert_smart_material(position, res)` -> `GroupLayerNode` | ✅ | ✅ | `ValueError` for a resource without smart material usage |
| Smart mask | `insert_smart_mask(position, res)` | ✅ | ✅ | `ValueError` for an invalid position, or a resource without `Usage.SMART_MASK` |
| Delete a node | `delete_node(node)` | ✅ | ✅ | |
| **Add a black or white mask** | `LayerNode.add_mask(MaskBackground.Black/White)` | ✅ | ✅ | `ValueError` if the layer already has a mask |
| Remove a mask, change its background, enable or disable it | `remove_mask()`, `set_mask_background()`, `enable_mask()`, `has_mask()`, `is_mask_enabled()` | ✅ | ✅ | `ValueError` if the layer has no mask |
| Blend mode | `Node.get/set_blending_mode(mode, channel=None)` and the `BlendingMode` enum | ✅ | ✅ | Per channel on layers and effects. `channel=None` for nodes in a mask stack. `ValueError` if the wrong form is used. Check `has_blending()`. |
| Opacity | `Node.get/set_opacity(opacity, channel=None)` (0.0–1.0) | ✅ | ✅ | Same channel rule as blend mode |
| Rename, show or hide | `set_name()`, `set_visible()` | ✅ | ✅ | |
| Fill sources, active channels, projection | `FillLayerNode/FillEffectNode.set_source / set_material_source / set_sources_from_preset / active_channels / set_projection_mode/parameters` | ✅ | ✅ | |
| Fill symmetry | `get/set_symmetry_parameters`, `set_symmetry_enabled`, `is_3d_projection_mode()` | ✅ (new in 0.3.5) | ✅ | Only for 3D projection modes |
| Read the selection | `get_selected_nodes(stack)`, `get_selection_type(layer)` | ✅ | ✅ | `get_selection_type`: `ValueError` if the layer is not in the active texture set |
| Set the selection (layers/effects, Content/Mask/GeometryMask/Properties) | `set_selected_nodes(nodes)`, `set_selection_type(layer, SelectionType.X)` | ✅ | ✅ | `ValueError` if the node is not in the active texture set. **`RuntimeError` inside `ScopedModification`.** |
| Geometry mask (mesh / UV tile) | `set_geometry_mask_type`, `set_geometry_mask_enabled_meshes/uv_tiles` | ✅ | ⚠️ deprecated | |
| Geometry mask (unified, include/exclude) | `get/set_geometry_mask(GeometryMask*Params)` | ❌ | ✅ (0.3.7) | Code for both versions should use the old setters or branch on the version |
| Save smart material or mask to the shelf | `create_smart_material(...)`, `create_smart_mask(layer, name)` | ✅ | ✅ | |
| Export smart material or mask to a path | `export_as_smart_material(...)`, `export_as_smart_mask(layer, name, path)` | ❌ | ✅ (0.3.6) | |
| **Group changes into one undo step** | `layerstack.ScopedModification(name)` | ⚠️ (bug outside the block, see below) | ✅ | |
| Pause the engine (performance only) | `application.disable_engine_computations()` (context manager) | ✅ | ✅ | Does not group undo |
| Move or reorder an existing node | none | ❌ | ❌ | The edition API has only insert and delete |
| Duplicate a layer | none (only `instantiate`, which makes an instance) | ❌ | ❌ | |
| Paint strokes | none | ❌ | ❌ | "Strokes are not accessible from the Python API" |
| Call undo/redo, read or limit history | none | ❌ | ❌ | See the 2026 feature request below |

Sources for the table:
[Layerstack edition](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/edition) ·
[Layerstack navigation](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/navigation) ·
[Layerstack selection](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/selection) ·
[Fill](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/fill) ·
[Paint](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/paint) ·
[Generator](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/generator) ·
[Filter](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/filter) ·
[Smart mask](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/smartmask) ·
[Smart material](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/smartmaterial) ·
[Stack](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/textureset-module/stack) ·
[application](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/application) ·
[Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog)

## Undo grouping: `ScopedModification` (verified)

From [Layerstack edition](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/edition):

- `class substance_painter.layerstack.ScopedModification(name)`. A context manager used with `with`. `name` is the label shown in the History window.
- Every layer stack call inside the block becomes **one history entry**, so one undo reverts all of it.
- Computation runs once, when the block exits. Without the block, each call makes its own history entry and its own texture update. The docs' example gets 1 entry and 1 update instead of 6.
- Introduced in 10.0: "[Python] Allow to batch actions to have a single undo/redo" ([10.0 notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/old-versions/version-10-0)).

Limits that affect the Workflow design:

1. **Selection changes are forbidden inside the block.** `set_selected_nodes` and `set_selection_type` raise `RuntimeError` "if called from within a ScopedModification section" ([Selection](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/selection)). A Workflow must run its selection Steps before or after the scope. If it does, one Ctrl+Z only covers the layer stack edits, not the selection change.
2. **Coverage beyond `layerstack` is not documented.** The docs describe the scope only for layer stack changes. The 12.0.2 fix "Unexpected error when adding a channel with scoped modification" suggests that `textureset` channel edits inside a scope are at least used. It is not documented whether things like project, baking, export, or brush/tool changes join the group.
3. **Painter 11.1.0 bug:** "Unexpected error when editing layer stack outside of scoped modification block" was fixed in **11.1.1** ([All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes)). On 11.1.0 the safe path is to do every layer stack edit inside a `ScopedModification`, or to update to 11.1.1 or later (11.1.3 is the last 11.1.x).
4. **Engine pause is a different feature:** `application.disable_engine_computations()` only stops texture computation. Undo is not mentioned ([application](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/application)).
5. **No undo system access:** a May 2026 Adobe Community feature request asks for "Python API access to the undo system" (a plugin creating too many undo steps). It has no Adobe reply ([feature request](https://community.adobe.com/feature-requests-60/access-to-the-undo-system-via-the-applications-preferences-and-scripting-1560890)). This is a user post, not documentation, but it matches the API reference, which has no undo or redo functions.

Sketch of the Workflow pattern this suggests (my code, not from the docs):

```python
import substance_painter as sp

def run_workflow(name, steps):
    stack = sp.textureset.get_active_stack()      # may raise ProjectError / RuntimeError
    with sp.layerstack.ScopedModification(name):  # one Ctrl+Z
        for step in steps:
            step(stack)                           # exception -> leaves the with block
    # selection changes only here, outside the scope
```

## Error behaviour (verified where cited)

| Situation | What happens | Source |
|---|---|---|
| No project open | `ProjectError` ("If no project is opened") from `get_active_stack` and every `Stack` method | [Stack](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/textureset-module/stack), [exception](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/exception) |
| Project open but no active stack | `RuntimeError` from `get_active_stack()` | helpx textureset page (index text, see Uncertain) |
| Painter services not started yet | `ServiceNotFoundError` | same, and the [exception](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/exception) module |
| Project not ready | Use `project.is_in_edition_state()`. Adobe's own example checks it before touching the layer stack. | [project](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/project), [save-selection example](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/examples/save-selection) |
| Nothing selected | `get_selected_nodes` returns a list. What it returns when nothing is selected is not documented, but an empty list is the obvious reading. | [Selection](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/selection) |
| Node not in the active texture set | `ValueError` from `get/set_selection_type`, `set_selected_nodes` | Selection |
| Bad insert position or wrong resource usage | `ValueError` | Edition / layer pages |
| Mask already exists or is missing | `ValueError` from `add_mask` / `remove_mask` and the other mask methods | Navigation |
| Stale node (uid no longer valid) | `ValueError` on any `Node` method | Navigation |

## Uncertain / not verified

- **What a `ScopedModification` does when an exception is raised inside it** (rollback, or a partial history entry) is not documented. This matters for "if a Step fails, the Workflow stops". It must be tested in Painter on both versions.
- **Whether `ScopedModification` blocks can be nested** is not documented.
- **`get_active_stack` exception list**: read from search-engine index text of the helpx textureset page, because helpx answered 403 to automated fetching. The index text also noted that the page's extracted Raises sections are scrambled. Confirm in Painter (Help > Scripting documentation > Python API, which is bundled locally with each version).
- **12.2.0 = API 0.3.7** is an inference: 12.2 has no changelog or release note item for Python. The bundled docs in 12.2.0 should be checked.
- The online reference is titled "Python API 0.3.5 Documentation" but already contains 0.3.7 items (geometry mask params), so the title is out of date. Since no page carries "added in" markers, the **version-locally bundled docs** are the best per-version source.
- Whether a selection change is recorded in history at all, so that one Ctrl+Z after a Workflow undoes the layer edits and not only a selection, is untested.
- Python version on 11.1.0: 12.0.0 moved to Python 3.13. The 11.x Python version was not checked here. Check with `sys.version` in both versions.
- A search summary placed the fix "[Python] Effects on GroupLayerNode cannot be found" in 10.1.2, while the All Changes read placed it in 11.0.0. This is minor either way, because both target versions are newer.

## Implications for the spec (for the map)

- One code base works on both versions. Layer stack Steps use the same calls. Version branching is needed only for the geometry mask API (0.3.7) and for smart material/mask export to disk (0.3.6).
- "One Ctrl+Z per Workflow" is possible for layer stack Steps through `ScopedModification`. Selection Steps must run outside the scope.
- On 11.1.0, wrap every layer stack edit in a `ScopedModification` (because of the 11.1.1 fix), or require 11.1.1 or later.
- Before running anything, check `project.is_open()` / `is_in_edition_state()` and catch `ProjectError` / `RuntimeError` / `ValueError` / `ServiceNotFoundError`, so a Step can fail with a clear message.
