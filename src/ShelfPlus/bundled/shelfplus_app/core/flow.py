"""Pure layout decisions for the Panel (PRD R2.3). No Qt: sizes are plain numbers in pixels.

The flat row does not cut Buttons off: it scrolls left and right.
"""

TALL = "tall"
FLAT = "flat"

# A Panel turns flat when it is at least this many times as wide as tall, and turns
# tall again only below LEAVE_FLAT_RATIO, so it does not flip back and forth at the edge.
ENTER_FLAT_RATIO = 2.0
LEAVE_FLAT_RATIO = 1.6


def orientation(width, height, current=None):
    """``"flat"`` (Groups side by side in one row) or ``"tall"`` (Groups stacked)."""
    if width <= 0 or height <= 0:
        return TALL
    ratio = LEAVE_FLAT_RATIO if current == FLAT else ENTER_FLAT_RATIO
    return FLAT if width >= height * ratio else TALL


def grid_columns(width, tile, spacing):
    """How many tiles of ``tile`` px fit side by side, ``spacing`` px apart (at least one)."""
    return max(1, (width + spacing) // (tile + spacing))


def edge_scroll(pos, length, edge, step):
    """How far to scroll while a Button is dragged at ``pos`` along an area ``length`` px
    long: ``-step`` within ``edge`` px of its start, ``+step`` near its end, else 0."""
    if length < 2 * edge or not 0 <= pos < length:
        return 0
    if pos < edge:
        return -step
    if pos >= length - edge:
        return step
    return 0


def drop_index(rects, x, y):
    """Where a Button dropped at ``(x, y)`` goes among tiles laid out row by row.

    ``rects`` are the tiles' ``(x, y, width, height)`` in order. The result is the
    position to insert before (``len(rects)`` = at the end).
    """
    for index, (left, top, width, height) in enumerate(rects):
        if y < top:
            return index
        if y < top + height and x < left + width / 2:
            return index
    return len(rects)
