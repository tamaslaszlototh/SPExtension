"""The Workflow editor's layer-block tree (PRD R7.2, R7.3), without Qt.

The Layout and the runner keep a Workflow as a flat ``steps[]``; the editor draws it as
blocks, read from the order:

- the **Start block**: the Steps before the first header, acting on the layer selected
  when the Workflow starts;
- one **block** per **header**, a Step that creates a layer (``add_layer``, a smart
  material) or picks one (``select_layer``), with the Steps that act on that layer;
- the **end section** ("At the end of the Workflow"): the UI Steps (``select_brush``,
  ``run_action``, ``save``).

Every function takes and returns flat lists; a change that breaks the rules returns
``None`` (the editor snaps the Step back). The lists returned are in normal order: a UI
Step written among the layer Steps (by hand) is moved to the end section.
"""

from typing import NamedTuple

from .workflow import UI_STEP_TYPES

START = "start"  # the Start block's title row
HEADER = "header"
STEP = "step"
END = "end"  # the end section's title row

HEADER_KIND, ACTING_KIND, UI_KIND = "header", "acting", "ui"


def kind_of(step):
    """``"header"``, ``"ui"`` or ``"acting"`` (acts on the Current layer)."""
    kind = step.get("type")
    if kind in UI_STEP_TYPES:
        return UI_KIND
    if kind in ("add_layer", "select_layer") or (kind == "add_smart" and step.get("smart") == "material"):
        return HEADER_KIND
    return ACTING_KIND


class Row(NamedTuple):
    """One line of the tree. ``index``: the Step's place in the flat list (``None`` for
    the two title rows). ``block``: ``"start"``, the block number, or ``"end"``."""

    kind: str
    index: object
    block: object


# -- the tree, as flat indices ---------------------------------------------------------


class _Tree:
    def __init__(self, steps):
        self.steps = list(steps)
        self.start, self.blocks, self.end = [], [], []
        for index, step in enumerate(self.steps):
            kind = kind_of(step)
            if kind == UI_KIND:
                self.end.append(index)
            elif kind == HEADER_KIND:
                self.blocks.append([index])
            elif self.blocks:
                self.blocks[-1].append(index)
            else:
                self.start.append(index)

    def order(self):
        return self.start + [i for block in self.blocks for i in block] + self.end

    def flat(self):
        return [self.steps[i] for i in self.order()]

    def block_of(self, index):
        """``"start"``, a block number, or ``"end"``."""
        if index in self.start:
            return START
        if index in self.end:
            return END
        return next(n for n, block in enumerate(self.blocks) if index in block)

    def is_header(self, index):
        return any(block[0] == index for block in self.blocks)

    def members(self, block):
        """The list holding a block's acting Steps (a header block: after its header)."""
        if block == START:
            return self.start
        if block == END:
            return self.end
        return self.blocks[block]

    def place(self, block, position, index):
        """Put ``index`` at ``position`` among the block's Steps (a header block: after the header)."""
        members = self.members(block)
        offset = 0 if block in (START, END) else 1
        members.insert(offset + position, index)

    def remove(self, index):
        for members in [self.start, self.end, *self.blocks]:
            if index in members:
                members.remove(index)
                return


def normalized(steps):
    """``steps`` in the order the tree draws them."""
    return _Tree(steps).flat()


def rows(steps, dragging=False):
    """The tree as rows, in execution order. The Start block's title is shown only when
    it has Steps, or while dragging (it is always a drop target then); the end section's
    title always."""
    tree = _Tree(steps)
    out = []
    if tree.start or dragging:
        out.append(Row(START, None, START))
        out.extend(Row(STEP, i, START) for i in tree.start)
    for number, block in enumerate(tree.blocks):
        out.append(Row(HEADER, block[0], number))
        out.extend(Row(STEP, i, number) for i in block[1:])
    out.append(Row(END, None, END))
    out.extend(Row(STEP, i, END) for i in tree.end)
    return out


# -- deleting ----------------------------------------------------------------------


def block_size(steps, index):
    """How many Steps a header's X deletes with it (0 for any other Step)."""
    tree = _Tree(steps)
    if not tree.is_header(index):
        return 0
    return len(tree.blocks[tree.block_of(index)]) - 1


def delete(steps, index):
    """Without the Step; a header takes its whole block with it."""
    tree = _Tree(steps)
    if tree.is_header(index):
        del tree.blocks[tree.block_of(index)]
    else:
        tree.remove(index)
    return tree.flat()


# -- moving with up / down -----------------------------------------------------------


def _swap_blocks(tree, number, other):
    if not 0 <= other < len(tree.blocks):
        return None
    tree.blocks[number], tree.blocks[other] = tree.blocks[other], tree.blocks[number]
    return tree.flat()


def _shift(steps, index, delta):
    tree = _Tree(steps)
    if tree.is_header(index):
        number = tree.block_of(index)
        return _swap_blocks(tree, number, number + delta)
    order = tree.order()
    position = order.index(index)
    other = position + delta
    if not 0 <= other < len(order):
        return None
    # an acting Step may pass a header (it changes block) but never a UI Step, and the
    # other way round
    if (kind_of(tree.steps[order[other]]) == UI_KIND) != (kind_of(tree.steps[index]) == UI_KIND):
        return None
    order[position], order[other] = order[other], order[position]
    return [tree.steps[i] for i in order]


def move_up(steps, index):
    """One row up: an acting Step past the Step or header above it (into the block above,
    or the Start block); a header with its block above the previous block; a UI Step
    within the end section. ``None`` if it cannot move."""
    return _shift(steps, index, -1)


def move_down(steps, index):
    """One row down, like ``move_up``."""
    return _shift(steps, index, +1)


# -- dragging ----------------------------------------------------------------------


def drop(steps, source, gap):
    """``steps`` with the Step at ``source`` dragged to ``gap`` of ``rows(steps,
    dragging=True)`` (gap g is just above row g). A header brings its whole block and
    lands only between blocks; an acting Step joins the block it lands in; a UI Step
    stays in the end section. ``None``: the drop breaks a rule and snaps back."""
    tree = _Tree(steps)
    drawn = rows(steps, dragging=True)
    gap = max(0, min(gap, len(drawn)))
    if tree.is_header(source):
        if gap == len(drawn) or drawn[gap].kind not in (HEADER, END):
            return None
        number = tree.block_of(source)
        moved = tree.blocks[number]
        before = None if drawn[gap].kind == END else tree.blocks[drawn[gap].block]
        if before is moved:
            return tree.flat()
        tree.blocks.remove(moved)
        tree.blocks.insert(len(tree.blocks) if before is None else tree.blocks.index(before), moved)
        return tree.flat()

    block = START if gap == 0 else drawn[gap - 1].block
    if (block == END) != (kind_of(tree.steps[source]) == UI_KIND):
        return None
    position = sum(1 for row in drawn[:gap] if row.kind == STEP and row.block == block and row.index != source)
    tree.remove(source)
    tree.place(block, position, source)
    return tree.flat()


# -- adding by hand ----------------------------------------------------------------


def insert(steps, step, selected=None):
    """``(steps, index of the new Step)`` with ``step`` added by the R7.3 rules: a header
    becomes a new block after the last one; a UI Step goes to the end of the end section;
    an acting Step to the end of the selected row's block, or of the last block when
    nothing (or a UI Step) is selected (the Start block when there is no block)."""
    tree = _Tree(steps)
    new = len(tree.steps)
    tree.steps.append(step)
    kind = kind_of(step)
    if kind == HEADER_KIND:
        tree.blocks.append([new])
    elif kind == UI_KIND:
        tree.end.append(new)
    else:
        block = None
        if selected is not None and 0 <= selected < new:
            block = tree.block_of(selected)
        if block is None or block == END:
            block = len(tree.blocks) - 1 if tree.blocks else START
        tree.members(block).append(new)
    return tree.flat(), tree.order().index(new)
