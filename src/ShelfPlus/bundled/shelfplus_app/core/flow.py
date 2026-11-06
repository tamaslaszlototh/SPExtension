"""Pure layout decisions for the Panel (PRD R2.3). No Qt: sizes are plain numbers in pixels."""

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


def _row_width(groups, counts, tile, spacing, gap):
    total = 0
    for index, ((header, _), count) in enumerate(zip(groups, counts)):
        if index:
            total += gap
        total += header + count * (spacing + tile)
    return total


def fit_flat_row(available, groups, tile, spacing, gap, overflow_width):
    """How many tiles of each Group fit in one row of ``available`` px.

    ``groups`` is a list of ``(header_width, button_count)``; a Group's width is its
    header plus ``spacing + tile`` per tile, and Groups are ``gap`` apart. If not
    everything fits, the » overflow button (``spacing + overflow_width``) is placed at
    the end of the row and tiles are cut until it fits too.

    Returns one entry per Group: the number of visible tiles, or ``None`` if not even
    the Group's header fits (then that Group and every later one go into the » menu).
    """
    counts = [count for _, count in groups]
    if _row_width(groups, counts, tile, spacing, gap) <= available:
        return counts

    budget = available - spacing - overflow_width
    result = []
    used = 0
    hidden = False
    for index, (header, count) in enumerate(groups):
        start = used + (gap if index else 0) + header
        if hidden or start > budget:
            hidden = True
            result.append(None)
            continue
        used = start
        shown = 0
        while shown < count and used + spacing + tile <= budget:
            used += spacing + tile
            shown += 1
        result.append(shown)
        if shown < count:
            hidden = True  # later Groups would sit after the cut tiles
    return result


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
