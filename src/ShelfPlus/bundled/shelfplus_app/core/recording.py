"""Recording (PRD R8), without Qt or Painter: the user works in Painter while the Panel
watches, and what they did becomes Steps.

The parts, all pure except the last:

- **Snapshots** of the active layer stack, as plain dicts the adapter builds::

      {"stack": "coat/main", "selected": <layer uid or None>, "nodes": [node, ...]}

  Nodes are listed top first (Painter's order) and refer to each other by uid, which
  stays the same across undo and redo. A node has ``uid``, ``name``, ``kind``,
  ``parent`` (a uid or ``None``) and ``stack``: ``"layers"`` for a layer (in the root or
  a folder), ``"content"`` or ``"mask"`` for an effect inside its parent layer. A layer
  also has ``mask`` (``None``, ``"black"``, ``"white"``, or ``"on"`` when Painter does
  not say which), ``blend`` and ``opacity`` (channel -> blend mode name / 0..1); an
  effect has ``source`` (the generator's or filter's ``resource://`` URL, or ``None``).
  A Fill or Paint layer and a Fill effect on a layer have ``channels`` (the ChannelType
  names switched on); a Fill layer or Fill effect has ``content`` in a Step's own form:
  ``{"material": url}``, ``{"sources": {channel: source}}`` or, a Fill on a mask,
  ``{"source": source}``; a source is ``{"color": "#rrggbb"}``, ``{"value": n}`` or
  ``{"resource": url}``.
- ``diff(before, after)``: what changed, as ``Change``\\ s.
- ``history_event(before, after)``: reading Painter's History (the ``QUndoView`` rows):
  a new row is an operation, the index going down is undo, up without a new row redo.
- ``derive(base, ops, final)``: the Steps of the operations still done (an undone one is
  simply left out), with the merging, filtering and selection rules of R8.5 and R8.6.
- ``Recording``: one Recording in progress. It listens to the adapter, takes a
  snapshot on every History signal (and, debounced, on Painter's layer stack event),
  and keeps the list of operations in step with the History.
"""

import logging
import time
from collections import Counter
from dataclasses import dataclass, field

from .workflow import SCOPE_PREFIX
from .channels import value_range
from .workflow_draft import resource_name

log = logging.getLogger("ShelfPlus.app.recording")

# -- diff --------------------------------------------------------------------------

ADDED, REMOVED, MOVED, NAME, MASK, BLEND, OPACITY, SOURCE, CHANNELS, CONTENT = (
    "added", "removed", "moved", "name", "mask", "blend", "opacity", "source", "channels", "content",
)
LAYERS = "layers"  # a node's ``stack`` when it is a layer, not an effect
DEFAULT_OPACITY = 1.0  # a channel a snapshot does not list


@dataclass(frozen=True)
class Change:
    """``old`` / ``new``: the values (an added node: ``new`` is the node; a removed one:
    ``old``). ``size``: how many nodes came with an added one (a smart material's)."""

    what: str
    uid: object
    old: object = None
    new: object = None
    size: int = 0


class Snapshot:
    """A snapshot with its nodes found by uid."""

    def __init__(self, raw):
        self.raw = raw
        self.stack = raw.get("stack")
        self.selected = raw.get("selected")
        self.order = [n["uid"] for n in raw.get("nodes", [])]
        self.nodes = {n["uid"]: n for n in raw.get("nodes", [])}

    def __contains__(self, uid):
        return uid in self.nodes

    def node(self, uid):
        return self.nodes.get(uid)

    def name(self, uid):
        node = self.nodes.get(uid)
        return node.get("name") if node else None

    def is_layer(self, uid):
        node = self.nodes.get(uid)
        return node is not None and node.get("stack") == LAYERS

    def place(self, uid):
        node = self.nodes[uid]
        return node.get("parent"), node.get("stack")

    def siblings(self, uid):
        """The nodes next to ``uid`` (same parent and stack), top first."""
        place = self.place(uid)
        return [u for u in self.order if self.place(u) == place]

    def below(self, uid):
        """The node just under ``uid`` among its siblings, or ``None``."""
        siblings = self.siblings(uid)
        index = siblings.index(uid)
        return siblings[index + 1] if index + 1 < len(siblings) else None

    def layer_of(self, uid):
        """The layer a node belongs to (itself for a layer)."""
        node = self.nodes.get(uid)
        while node is not None and node.get("stack") != LAYERS:
            node = self.nodes.get(node.get("parent"))
        return node["uid"] if node else None

    def count(self, name):
        return sum(1 for n in self.nodes.values() if n.get("stack") == LAYERS and n.get("name") == name)


def _snapshot(value):
    return value if isinstance(value, Snapshot) else Snapshot(value)


def _changed_channels(old, new, default=None):
    old, new = old or {}, new or {}
    keys = [k for k in dict.fromkeys([*old, *new]) if old.get(k, default) != new.get(k, default)]
    return {k: old.get(k, default) for k in keys}, {k: new.get(k, default) for k in keys}


def diff(before, after):
    """The changes from ``before`` to ``after`` (two snapshots of the same stack)."""
    before, after = _snapshot(before), _snapshot(after)
    changes = []
    added = [u for u in after.order if u not in before]
    added_set = set(added)
    for uid in added:
        node = after.node(uid)
        if node.get("parent") in added_set:
            continue  # it came with its parent
        size = sum(1 for other in added if other != uid and _inside(after, other, uid))
        changes.append(Change(ADDED, uid, new=node, size=size))
    removed = {u for u in before.order if u not in after}
    for uid in before.order:
        if uid in removed and before.node(uid).get("parent") not in removed:
            changes.append(Change(REMOVED, uid, old=before.node(uid)))

    moved = set()
    for uid in before.order:
        if uid not in after:
            continue
        old, new = before.node(uid), after.node(uid)
        if before.place(uid) != after.place(uid):
            moved.add(uid)
        if old.get("name") != new.get("name"):
            changes.append(Change(NAME, uid, old.get("name"), new.get("name")))
        if old.get("mask") != new.get("mask"):
            changes.append(Change(MASK, uid, old.get("mask"), new.get("mask")))
        was, now = _changed_channels(old.get("blend"), new.get("blend"))
        if was:
            changes.append(Change(BLEND, uid, was, now))
        was, now = _changed_channels(old.get("opacity"), new.get("opacity"), DEFAULT_OPACITY)
        if was:
            changes.append(Change(OPACITY, uid, was, now))
        if old.get("source") != new.get("source"):
            changes.append(Change(SOURCE, uid, old.get("source"), new.get("source")))
        if old.get("channels") != new.get("channels"):
            changes.append(Change(CHANNELS, uid, old.get("channels"), new.get("channels")))
        if old.get("content") != new.get("content"):
            changes.append(Change(CONTENT, uid, old.get("content"), new.get("content")))

    # Order: the nodes present in both, compared among themselves (an insertion or a
    # removal shifts the others but does not move them).
    for uid in before.order:
        if uid not in after or uid in moved:
            continue
        common = [u for u in before.siblings(uid) if u in after and after.place(u) == before.place(u)]
        now = [u for u in after.siblings(uid) if u in set(common)]
        if common.index(uid) != now.index(uid):
            moved.add(uid)
            break  # one reorder is reported once
    changes.extend(Change(MOVED, uid) for uid in before.order if uid in moved)
    return changes


def _inside(snapshot, uid, ancestor):
    node = snapshot.node(uid)
    while node is not None:
        if node.get("parent") == ancestor:
            return True
        node = snapshot.node(node.get("parent"))
    return False


# -- History -------------------------------------------------------------------------

PUSH, UNDO, REDO, MERGE, NOTHING, RESET = "push", "undo", "redo", "merge", "nothing", "reset"


def history_event(before, after):
    """What happened between two readings of the History: each is ``(labels, index)``,
    the labels of its rows (without Qt's ``<empty>`` first row) and how many of them are
    done. Returns ``(kind, position, shift)``:

    - ``(PUSH, p, shift)``: new operations from row ``p`` on (rows from ``p`` that were
      there before, undone, are gone). ``shift`` = 1 when a full History dropped its
      oldest row to make room.
    - ``(UNDO, None, 0)`` / ``(REDO, None, 0)``: the same rows, the index down / up. (A
      new operation with the same label as an undone one looks like a redo here; the
      ``Recording`` tells them apart by the layer stack.)
    - ``(MERGE, None, 0)``: only the text of the last done row changed (Qt merged the
      next change into it, e.g. a slider still being dragged).
    - ``(NOTHING, None, 0)``; ``(RESET, None, 0)``: rows went away (a new project…).
    """
    labels_a, a = tuple(before[0]), before[1]
    labels_b, b = tuple(after[0]), after[1]
    if labels_a == labels_b:
        if b < a:
            return UNDO, None, 0
        if b > a:
            return REDO, None, 0
        return NOTHING, None, 0
    if labels_a and len(labels_a) == len(labels_b) == a == b and labels_b[:-1] == labels_a[:-1]:
        return MERGE, None, 0
    if labels_a and len(labels_a) == len(labels_b) == a == b and labels_b[:-1] == labels_a[1:]:
        return PUSH, len(labels_b) - 1, 1
    common = 0
    while common < min(len(labels_a), len(labels_b)) and labels_a[common] == labels_b[common]:
        common += 1
    if len(labels_b) > common and b > common:
        return PUSH, common, 0
    return RESET, None, 0


# -- naming ----------------------------------------------------------------------------

# QActions that only open a window or a view of the Assets window: never an operation's name.
WINDOW_ACTIONS = {
    "smart_masks_action", "smart_materials_action", "materials_action", "brushes_action",
    "alphas_action", "textures_action", "filters_action", "generators_action", "assets_action",
}
WINDOW_MENUS = ("Window", "Views")


def is_window_action(action):
    """Whether a command only opens a window or an Assets view (R8.5)."""
    if action.name in WINDOW_ACTIONS or action.name.endswith("_view_action"):
        return True
    return bool(action.path) and action.path[0] in WINDOW_MENUS


# -- operations -> Steps ---------------------------------------------------------------


@dataclass
class Op:
    """One operation of the History. ``name``: what a hook called it (the command clicked),
    if anything did; ``drops``: resources dropped onto Painter just before; ``skipped``:
    a notice when the whole operation is not recorded (another texture set…)."""

    label: str
    changes: list
    before: object
    after: object
    name: str = None
    drops: tuple = ()
    skipped: str = None

    @property
    def title(self):
        return self.name or self.label or "A change"

    def signature(self):
        """What a redo of it must do again, to tell a redo from a new operation."""
        return [(c.what, c.uid, c.new) for c in self.changes]


@dataclass
class Capture:
    """What a Recording captured: the Steps, and the notices about what it skipped."""

    steps: list
    notices: list = field(default_factory=list)


EFFECTS = ("generator", "filter", "levels", "anchor", "fill", "paint")
LAYER_KINDS = ("fill", "paint", "folder")
PAINTING = ("stroke",)  # History labels of painting (``Add stroke``): never a Step, never reported

UNKNOWN = "“{}” cannot be recorded, so it was skipped."
NOT_RECORDED = "{} cannot be recorded, so it was skipped."
MOVING = NOT_RECORDED.format("Moving layers")
DELETING = NOT_RECORDED.format("Deleting existing layers or effects")
RENAMING = NOT_RECORDED.format("Renaming existing layers")
EXISTING_EFFECT = NOT_RECORDED.format("Changing an existing effect")
EXISTING_CONTENT = NOT_RECORDED.format("Changing the channels or content of an existing layer")
TWIN_NAMES = "Several layers are named “{}”: the Select layer Step will stop there. Rename one of them."


class _Block:
    """``key``: the layer uid the block acts on; ``header``: its Step (``None`` for the
    Start block)."""

    def __init__(self, key, header):
        self.key, self.header, self.steps = key, header, []

    @property
    def selects(self):
        return self.header is not None and self.header["type"] == "select_layer"


def _percent(value):
    number = round(float(value) * 100, 1)
    return int(number) if number == int(number) else number


def _most_common(values):
    values = [v for v in values if v is not None]
    return Counter(values).most_common(1)[0][0] if values else None


class _Build:
    def __init__(self, base, notices):
        self.base = _snapshot(base)
        self.start = self.base.selected
        self.start_block = _Block(self.start, None)
        self.blocks = []
        self.current = self.start_block
        self.of_layer = {}  # layer uid -> its block (a new layer's, or a select_layer one)
        self.created = {}  # uid of a node made during the Recording -> its Step
        self.masks, self.blends, self.opacities = {}, {}, {}  # layer uid -> the Step
        self.origin = {}  # (uid, "blend") / (uid, "opacity", channel) -> the value before
        # a new node's channels and content: what it started with, and what it has now
        self.content_origin, self.content_now = {}, {}
        self.notices = notices

    def notice(self, text):
        if text not in self.notices:
            self.notices.append(text)

    # -- where a Step goes ---------------------------------------------------------

    def block_for(self, uid, op):
        """The block of Steps acting on layer ``uid``; it becomes the current one."""
        if self.current.key == uid:
            return self.current
        block = self.of_layer.get(uid)
        if block is None and uid == self.start:
            block = self.start_block
        if block is None:
            block = self._select(uid, op)
        self.current = block
        return block

    def _select(self, uid, op):
        name = _snapshot(op.before).name(uid) or _snapshot(op.after).name(uid)
        block = _Block(uid, {"type": "select_layer", "name": name})
        self.blocks.append(block)
        self.of_layer[uid] = block
        if self.base.count(name) > 1 or _snapshot(op.after).count(name) > 1:
            self.notice(TWIN_NAMES.format(name))
        return block

    def act(self, uid, step, op):
        self.block_for(uid, op).steps.append(step)

    def remove(self, step):
        for block in [self.start_block, *self.blocks]:
            if any(s is step for s in block.steps):
                block.steps = [s for s in block.steps if s is not step]
                return

    # -- one operation ---------------------------------------------------------------

    def apply(self, op):
        if op.skipped:
            self.notice(op.skipped)
            return
        if not op.changes:
            if not any(word in (op.label or "").lower() for word in PAINTING):
                self.notice(UNKNOWN.format(op.title))
            return
        smart_masks = set()
        if "drop resource" in (op.label or "").lower():
            smart_masks = {
                c.new.get("parent") for c in op.changes
                if c.what == ADDED and c.new.get("stack") == "mask"
            }
        for change in op.changes:
            handler = getattr(self, "_" + change.what)
            handler(op, change, smart_masks)

    def _added(self, op, change, smart_masks):
        node = change.new
        if node.get("stack") == LAYERS:
            self._new_layer(op, change)
            return
        layer = node.get("parent")
        if node.get("stack") == "mask" and layer in smart_masks:
            step = {"type": "add_smart", "smart": "mask"}
        elif node.get("kind") in EFFECTS:
            step = {"type": "add_effect", "effect": node["kind"], "target": "mask" if node.get("stack") == "mask" else "layer"}
            if node.get("source"):
                step["resource"] = node["source"]
                if node.get("name"):
                    step["resource_name"] = node["name"]
        else:
            self.notice(UNKNOWN.format(op.title))
            return
        self.act(layer, step, op)
        self.created[change.uid] = step
        self._remember(change.uid, node)

    def _new_layer(self, op, change):
        node, uid = change.new, change.uid
        if node.get("kind") == "folder" and change.size:
            name = node.get("name") or ""
            url = next((u for u in reversed(op.drops) if resource_name(u) == name), "")
            step = {"type": "add_smart", "smart": "material", "resource": url, "resource_name": name}
        elif node.get("kind") in LAYER_KINDS:
            step = {"type": "add_layer", "layer": node["kind"]}
        else:
            self.notice(UNKNOWN.format(op.title))
            return
        # Painter puts a new layer above the selected one; the Workflow puts it above its
        # Current layer. So: above another existing layer, that layer is selected first;
        # above the start layer, its block runs first (the layers made after it then go
        # above it, as in Painter); above an earlier new layer, its block runs right
        # after that layer's.
        below = _snapshot(op.after).below(uid)
        last = self.blocks[-1] if self.blocks else self.start_block
        position = len(self.blocks)
        if below is not None and below == self.start and self.blocks:
            position = 0
        elif below in self.created and self.of_layer.get(below) not in (None, last):
            position = self.blocks.index(self.of_layer[below]) + 1
        elif below is not None and below in self.base and below != self.start and below not in self.created:
            if not (last.selects and last.key == below):
                self._select(below, op)
                position = len(self.blocks)
        block = _Block(uid, step)
        self.blocks.insert(position, block)
        self.of_layer[uid] = block
        self.current = block
        self.created[uid] = step
        for channel, mode in (node.get("blend") or {}).items():
            self.origin.setdefault((uid, BLEND), mode)
        for channel, value in (node.get("opacity") or {}).items():
            self.origin.setdefault((uid, OPACITY, channel), _percent(value))
        self._remember(uid, node)

    # -- a new layer's channels and content ---------------------------------------------

    def _remember(self, uid, node):
        """What a new node started with: only what changes from it is recorded."""
        start = {"channels": node.get("channels"), "content": node.get("content")}
        self.content_origin[uid] = start
        self.content_now[uid] = dict(start)

    def _channels(self, op, change, smart_masks):
        self._content_change(op, change, "channels")

    def _content(self, op, change, smart_masks):
        self._content_change(op, change, "content")

    def _content_change(self, op, change, key):
        uid = change.uid
        if uid not in self.created:
            self.notice(EXISTING_CONTENT if _snapshot(op.after).is_layer(uid) else EXISTING_EFFECT)
            return
        if uid in self.content_now:
            self.content_now[uid][key] = change.new
            self._sync_content(uid)

    def _sync_content(self, uid):
        """The new node's Step gets its channels and content as they are now, compared
        with what it started with (switched back: nothing is stored)."""
        step = self.created[uid]
        takes_channels, takes_content = _content_slots(step)
        origin, now = self.content_origin[uid], self.content_now[uid]
        for key in ("channels", "material", "sources", "source"):
            step.pop(key, None)
        if takes_channels and now["channels"] and now["channels"] != origin["channels"]:
            step["channels"] = list(now["channels"])
        new, old = now["content"] or {}, origin["content"] or {}
        if new == old:
            return
        if takes_content == "layer" and new.get("material"):
            step["material"] = {"resource": new["material"]}
        elif takes_content == "layer" and "sources" in new:
            was = old.get("sources") or {}
            changed = {ch: _in_range(ch, s) for ch, s in new["sources"].items() if was.get(ch) != s}
            if "channels" in step:
                changed = {ch: s for ch, s in changed.items() if ch in step["channels"]}
            if changed:
                step["sources"] = changed
        elif takes_content == "mask" and new.get("source"):
            step["source"] = _in_range(None, new["source"])

    def _removed(self, op, change, smart_masks):
        step = self.created.pop(change.uid, None)
        if step is None:
            self.notice(DELETING)
            return
        block = self.of_layer.get(change.uid)
        if block is not None and block.header is step:
            self.blocks.remove(block)
            del self.of_layer[change.uid]
            if self.current is block:
                self.current = self.blocks[-1] if self.blocks else self.start_block
            return
        self.remove(step)

    def _moved(self, op, change, smart_masks):
        self.notice(MOVING)

    def _name(self, op, change, smart_masks):
        if not _snapshot(op.after).is_layer(change.uid):
            return  # effects rename themselves (``Generator (empty)`` -> ``Dirt``)
        step = self.created.get(change.uid)
        if step is None:
            self.notice(RENAMING)
        elif step["type"] == "add_layer":
            step["name"] = change.new

    def _mask(self, op, change, smart_masks):
        uid = change.uid
        if uid in smart_masks:
            return  # the smart mask Step makes its own mask
        if change.old is None and change.new is not None:
            background = change.new
            if background not in ("black", "white"):
                background = "white" if "white" in op.title.lower() else "black"
            step = {"type": "add_mask", "background": background}
            self.act(uid, step, op)
            self.masks[uid] = step
        elif change.new is None and uid in self.masks:
            self.remove(self.masks.pop(uid))
        else:
            self.notice(UNKNOWN.format(op.title))

    def _blend(self, op, change, smart_masks):
        uid = change.uid
        if not _snapshot(op.after).is_layer(uid):
            self.notice(UNKNOWN.format(op.title))
            return
        self.origin.setdefault((uid, BLEND), _most_common(change.old.values()))
        mode = _most_common(change.new.values())
        step = self.blends.get(uid)
        if step is None:
            step = {"type": "set_blend", "blend": mode}
            self.act(uid, step, op)
            self.blends[uid] = step
        step["blend"] = mode

    def _opacity(self, op, change, smart_masks):
        uid = change.uid
        if not _snapshot(op.after).is_layer(uid):
            self.notice(UNKNOWN.format(op.title))
            return
        step = self.opacities.get(uid)
        if step is None:
            step = {"type": "set_opacity", "opacity": {}}
            self.act(uid, step, op)
            self.opacities[uid] = step
        for channel, value in change.new.items():
            self.origin.setdefault((uid, OPACITY, channel), _percent(change.old[channel]))
            step["opacity"][channel] = _percent(value)

    def _source(self, op, change, smart_masks):
        step = self.created.get(change.uid)
        if step is None or step["type"] != "add_effect":
            self.notice(EXISTING_EFFECT)
            return
        step.pop("resource_name", None)
        if change.new:
            step["resource"] = change.new
            name = _snapshot(op.after).name(change.uid)
            if name:
                step["resource_name"] = name
        else:
            step.pop("resource", None)

    # -- the end ---------------------------------------------------------------------

    def finish(self, final):
        for uid, step in self.blends.items():
            if step["blend"] == self.origin.get((uid, BLEND)):
                self.remove(step)
        for uid, step in self.opacities.items():
            values = step["opacity"]
            for channel in [c for c, v in values.items() if v == self.origin.get((uid, OPACITY, c))]:
                del values[channel]
            if not values:
                self.remove(step)
        # a select_layer with nothing after it in its block, and no new layer after it
        self.blocks = [
            b for i, b in enumerate(self.blocks)
            if not (b.selects and not b.steps and (i + 1 == len(self.blocks) or self.blocks[i + 1].selects))
        ]
        if final is not None:
            final = _snapshot(final)
            chosen = final.layer_of(final.selected) if final.selected is not None else None
            last = self.blocks[-1].key if self.blocks else self.start
            if chosen is not None and chosen != last and chosen in self.base and chosen != self.start and chosen not in self.created:
                self._select(chosen, Op("", [], final, final))

    def steps(self):
        flat = list(self.start_block.steps)
        for block in self.blocks:
            flat.append(block.header)
            flat.extend(block.steps)
        return [_copy(s) for s in flat]


def _content_slots(step):
    """``(takes channels, content kind)`` of a Step: a Fill layer and a Fill effect on a
    layer take channels and ``"layer"`` content (a material or per-channel sources), a
    Paint layer only channels, a Fill on a mask one ``"mask"`` source; others nothing."""
    kind = step.get("type")
    if kind == "add_layer":
        return step["layer"] in ("fill", "paint"), "layer" if step["layer"] == "fill" else None
    if kind == "add_effect" and step.get("effect") == "fill":
        return (True, "layer") if step.get("target") == "layer" else (False, "mask")
    return False, None


def _in_range(channel, source):
    """A uniform value kept inside its channel's range (a mask's: 0 to 1), rounded."""
    if "value" not in source:
        return dict(source)
    low, high = value_range(channel) if channel is not None else (0, 1)
    value = round(min(max(float(source["value"]), low), high), 3)
    return {"value": int(value) if value == int(value) else value}


def _copy(step):
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in step.items()}


def derive(base, ops, final=None):
    """The Steps of ``ops`` (the operations still done, oldest first) recorded from
    ``base`` (the snapshot when the Recording started: its selected layer is the start
    layer). ``final``: the snapshot at Stop, for the layer selected at the end."""
    notices = []
    build = _Build(base, notices)
    for op in ops:
        build.apply(op)
    build.finish(final)
    return Capture(build.steps(), notices)


# -- one Recording in progress ---------------------------------------------------------

DEBOUNCE_MS = 150  # Painter's layer stack event comes about twice per operation
RETRY_MS = 300  # the project is locked while it saves
RETRIES = 20
HINT_MS = 3000  # a command clicked this long before its History row names it
DROP_MS = 15000  # a resource dropped this long before a new smart material is its resource

OTHER_STACK = "Changes in another texture set cannot be recorded: a Workflow works on one texture set."
OWN_WORKFLOW = "Shelf+'s own Workflows are not recorded."
UNREADABLE = "Painter's layer stack could not be read, so a Step may be missing."
NO_PROJECT = "Open a project first: Recording watches its layer stack."
NO_HISTORY = "Painter's History could not be found, so Recording cannot start. See the log."


def _now_ms():
    return time.monotonic() * 1000


class Recording:
    """One Recording. ``start()`` hooks it up; ``stop()`` unhooks it and returns the
    ``Capture``. Meanwhile ``capture`` is what it has so far.

    The adapter side (see ``adapter/__init__.py``): ``snapshot()``,
    ``watch_history(callback(labels, index)) -> stop`` (called at once with the current
    state), ``on_layer_stack_changed(callback) -> stop``, ``on_project_closing(callback)
    -> stop``, ``watch_drops(callback(urls)) -> stop`` and ``later(ms, callback) -> timer``.
    Commands clicked come from the App (its ``ActionWatcher``) through ``command()``.

    ``changed()``: the Steps may have changed. ``notify(text)``: a new notice for the
    user. ``closing()``: the project is about to close (the App stops the Recording).
    """

    def __init__(self, adapter, changed=None, notify=None, closing=None, now=None):
        self.adapter = adapter
        self._changed = changed or (lambda: None)
        self._notify = notify or (lambda text: None)
        self._closing = closing or (lambda: None)
        self.now = now or _now_ms
        self.base = None
        self.stack = None  # the texture set it records
        self.closed = None  # the snapshot after the last History event: the next diff's start
        self.latest = None  # the last snapshot read at all
        self.history = None  # (labels, index) last handled
        self.origin = 0  # the History row of ops[0]
        self.ops = []  # one per History row since ``origin`` (None: part of the one before)
        self.fixed = []  # done operations whose History row is gone (they cannot be undone)
        self.done = 0  # how many of ``ops`` are done (not undone)
        self.capture = Capture([])
        self._pending = None  # a History reading waiting for a snapshot
        self._retry_timer = None
        self._retries = 0
        self._debounce = None
        self._hints = []  # (time, command label)
        self._drops = []  # (time, url)
        self._announced = set()
        self._stops = []
        self.active = False

    # -- starting and stopping -----------------------------------------------------

    def start(self):
        """Hook up. Returns why it cannot start (for the user), or ``None``."""
        try:
            ready = self.adapter.project_ready()
        except Exception:
            log.exception("Could not ask whether a project is ready")
            ready = False
        if not ready:
            return NO_PROJECT
        try:
            self.base = self.adapter.snapshot()
        except Exception:
            log.exception("The first snapshot failed")
            return UNREADABLE
        self.stack = self.base.get("stack")
        self.closed = self.base
        self.active = True
        try:
            self._stops.append(self.adapter.watch_history(self._on_history))
        except Exception:
            log.exception("Could not watch Painter's History")
            self.active = False
            return NO_HISTORY
        for hook, callback in (
            (self.adapter.on_layer_stack_changed, self._on_stack_changed),
            (self.adapter.on_project_closing, self._on_closing),
            (self.adapter.watch_drops, self.dropped),
        ):
            try:
                self._stops.append(hook(callback))
            except Exception:
                log.exception("Recording: could not hook %s", getattr(hook, "__name__", hook))
        log.info("Recording started on %r (%d nodes)", self.stack, len(self.base.get("nodes", [])))
        return None

    def stop(self):
        """Unhook and return the ``Capture``, with what changed since the last History
        row and the layer selected now."""
        if not self.active:
            return self.capture
        # The project may already be unreadable (closing, saving): then the last good
        # snapshot (the debounced layer stack event keeps it fresh) stands in.
        final = self._snapshot() or self.latest
        if final is not None and self._pending is not None:
            self._handle(final)
        self.active = False
        for stop in self._stops:
            try:
                stop()
            except Exception:
                log.exception("Recording: unhooking failed")
        self._stops = []
        for timer in (self._retry_timer, self._debounce):
            if timer is not None:
                timer.stop()
        ops = self._done_ops()
        if final is not None and final.get("stack") == self.stack and self.closed is not None:
            if self.closed.get("stack") == self.stack:
                changes = diff(self.closed, final)
                if changes:
                    ops.append(Op("", changes, self.closed, final, name=self._hint()))
        if final is None or final.get("stack") != self.stack:
            final = None
        self.capture = derive(self.base, ops, final)
        log.info("Recording stopped: %d Step(s), %d notice(s)", len(self.capture.steps), len(self.capture.notices))
        return self.capture

    # -- what it hears ---------------------------------------------------------------

    def command(self, action):
        """A command the user ran (the App's watcher already dropped duplicates and the
        plugin's own triggers)."""
        if self.active and not is_window_action(action):
            self._hints.append((self.now(), action.label))

    def dropped(self, urls):
        if self.active:
            self._drops.extend((self.now(), url) for url in urls)

    def _hint(self):
        """The command clicked just before, once."""
        now = self.now()
        hints = [label for when, label in self._hints if now - when <= HINT_MS]
        self._hints = []
        return hints[-1] if hints else None

    def _recent_drops(self):
        now = self.now()
        self._drops = [(when, url) for when, url in self._drops if now - when <= DROP_MS]
        return tuple(url for _, url in self._drops)

    def _on_closing(self):
        if self.active:
            log.info("The project is closing: the Recording stops")
            self._closing()

    def _on_stack_changed(self):
        if not self.active:
            return
        if self._debounce is not None:
            self._debounce.stop()
        self._debounce = self.adapter.later(DEBOUNCE_MS, self._settled)

    def _settled(self):
        """The layer stack event, debounced: a History reading still waiting for a
        snapshot (the project was locked) is handled now, and a texture set switch takes
        a new base."""
        self._debounce = None
        if not self.active:
            return
        snap = self._snapshot()
        if snap is None:
            return
        if self._pending is not None:
            self._retries = 0
            self._handle(snap)
        if self.closed is None or snap.get("stack") != self.closed.get("stack"):
            if snap.get("stack") != self.stack:
                self._announce(OTHER_STACK)
            log.info("Recording: texture set %r; new base snapshot", snap.get("stack"))
            self.closed = snap
        elif self._merge_into_top(snap):
            self._update()

    def _on_history(self, labels, index):
        if not self.active:
            return
        reading = (tuple(labels), index)
        if self.history is None:
            self.history = reading  # the state when the Recording started
            self.origin = index  # the next operation's row
            return
        self._pending = reading
        self._process()

    # -- keeping up with the History -----------------------------------------------------

    def _snapshot(self):
        try:
            snap = self.adapter.snapshot()
        except Exception as error:
            log.info("Recording: snapshot failed (%s)", error)
            return None
        self.latest = snap
        return snap

    def _process(self):
        if self._pending is None or not self.active:
            return
        snap = self._snapshot()
        if snap is None:
            if self._retries < RETRIES:
                self._retries += 1
                if self._retry_timer is None:
                    self._retry_timer = self.adapter.later(RETRY_MS, self._retry)
            else:
                self._announce(UNREADABLE)
                self._retries = 0
            return
        self._retries = 0
        self._handle(snap)

    def _retry(self):
        self._retry_timer = None
        self._process()

    def _handle(self, snap):
        reading, self._pending = self._pending, None
        before, self.history = self.history, reading
        kind, position, shift = history_event(before, reading)
        labels, index = reading
        log.debug("Recording: History %s (%d rows, index %d)", kind, len(labels), index)
        if kind == PUSH:
            self._push(position, shift, labels, index, snap)
        elif kind == UNDO:
            self.done = self._clamp(index - self.origin)
            self.closed = snap
        elif kind == REDO:
            self._redo(before[1], labels, index, snap)
        elif kind == RESET:
            self.origin = min(self.origin, len(labels))
            self.ops = self.ops[: len(labels) - self.origin]
            self.done = self._clamp(index - self.origin)
            self.closed = snap
        elif kind == MERGE:
            self._merge_into_top(snap, forced=True)
        else:
            self._merge_into_top(snap)  # a merge Qt signalled without a new text
        self._update()

    def _top(self):
        """The last done operation, or ``None``."""
        return next((o for o in reversed(self.ops[: self.done]) if o is not None), None)

    def _merge_into_top(self, snap, forced=False):
        """Changes since the last History row that continue it (the same parameter of the
        same node, e.g. the rest of a slider drag Painter merged into the row it made at
        the start) belong to that row, so an undo of a later row leaves them alone.
        ``forced``: the History said so. Other changes wait for the next row."""
        top = self._top()
        if top is None or not self._same_stack(snap) or top.skipped:
            return False
        changes = diff(self.closed, snap)
        if not changes:
            return False
        keys = {(c.what, c.uid) for c in top.changes}
        if not forced and not all((c.what, c.uid) in keys for c in changes):
            return False
        top.changes = diff(top.before, snap)
        top.after = snap
        self.closed = snap
        log.debug("Recording: %d change(s) merged into %r", len(changes), top.label)
        return True

    def _clamp(self, count):
        return max(0, min(count, len(self.ops)))

    def _push(self, position, shift, labels, index, snap):
        self.origin -= shift
        first = position - self.origin
        if first < 0:  # undone past the start of the Recording, then something new
            self.ops, self.origin, first = [], position, 0
        if self.origin < 0:  # a full History dropped the row of ops[0]: it stays done for good
            if self.ops and self.ops[0] is not None and self.done > 0:
                self.fixed.append(self.ops[0])
            self.ops, self.origin, first = self.ops[1:], 0, max(0, first - 1)
            self.done = max(0, self.done - 1)
        op = self._operation(labels[index - 1] if index else "", snap)
        self.ops = self.ops[:first] + [op] + [None] * max(0, index - position - 1)
        self.done = self._clamp(index - self.origin)
        self.closed = snap

    def _redo(self, previous, labels, index, snap):
        """A redo brings back exactly what the operation did; anything else is a new
        operation that happens to have the same label as the undone one."""
        redone = [o for o in self.ops[self._clamp(previous - self.origin): self._clamp(index - self.origin)] if o]
        changes = diff(self.closed, snap) if self._same_stack(snap) else []
        expected = [s for o in redone for s in o.signature()]
        if redone and [(c.what, c.uid, c.new) for c in changes] == expected:
            self.done = self._clamp(index - self.origin)
            self.closed = snap
            return
        self._push(previous, 0, labels, index, snap)

    def _same_stack(self, snap):
        return self.closed is not None and self.closed.get("stack") == snap.get("stack") == self.stack

    def _operation(self, label, snap):
        if (label or "").startswith(SCOPE_PREFIX):
            skipped = OWN_WORKFLOW
        elif snap.get("stack") != self.stack:
            skipped = OTHER_STACK
        elif not self._same_stack(snap):
            skipped = UNREADABLE
        else:
            skipped = None
        changes = [] if skipped else diff(self.closed, snap)
        return Op(label, changes, self.closed, snap, self._hint(), self._recent_drops(), skipped=skipped)

    def _done_ops(self):
        return self.fixed + [o for o in self.ops[: self.done] if o is not None]

    def _update(self):
        self.capture = derive(self.base, self._done_ops())
        for text in self.capture.notices:
            self._announce(text)
        self._changed()

    def _announce(self, text):
        if text not in self._announced:
            self._announced.add(text)
            self._notify(text)
