"""Timing of the pen hover helper (PRD R2.6), without Qt.

Qt's own tooltip does not appear with a pen in Painter, so the Panel polls the cursor
about every 100 ms and feeds what is under it to ``HoverTracker.tick``. The tracker
says when to show the element's name and when to hide it.
"""

SHOW = "show"
HIDE = "hide"


class HoverTracker:
    def __init__(self, delay_ms=600):
        self.delay_ms = delay_ms
        self._target = None
        self._since = 0
        self._shown = None  # the text currently shown, if any

    def tick(self, now_ms, target, text, showing=True):
        """``target`` is the Panel element under the cursor (``None`` outside the Panel),
        ``text`` its name, ``showing`` whether a tooltip is on screen (Qt hides it by
        itself after a while or on a click). Returns ``(SHOW, text)``, ``(HIDE,)`` or ``None``."""
        if target is not self._target:
            was_shown = self._shown is not None
            self._target, self._since, self._shown = target, now_ms, None
            return (HIDE,) if was_shown else None
        if self._shown is not None and not showing:
            self._since, self._shown = now_ms, None  # wait the delay again, then re-show
            return None
        if not text:
            was_shown = self._shown is not None
            self._shown = None
            return (HIDE,) if was_shown else None
        if target is None:
            return None
        if self._shown is None and now_ms - self._since < self.delay_ms:
            return None
        if self._shown == text:
            return None
        self._shown = text
        return (SHOW, text)
