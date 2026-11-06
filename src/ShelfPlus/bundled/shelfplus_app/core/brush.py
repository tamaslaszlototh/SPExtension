"""Brush buttons (PRD R5), without Qt or Painter: they are reached through the adapter.

- Creating: a drop from the Assets window carries ``text/uri-list`` with URL-encoded
  ``resource://`` URLs (``resource_urls_from_drop``). A Brush button stores the
  version-less URL and the display name (``brush_button``).
- The icon is read at drag time; ``pick_brush_icon`` picks the first source that has one.
- Activating is UI automation of the Assets window. There is no official API.
  ``select_brush`` is the ``select_brush`` Step: the Workflow runner calls it too.
"""

import base64
import binascii
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode

log = logging.getLogger("ShelfPlus.app.brush")

RESOURCE_SCHEME = "resource://"


@dataclass(frozen=True)
class BrushResource:
    """A brush preset or ``.abr`` brush as Painter knows it on this machine.

    ``url`` is version-less. ``handle`` is the adapter's own object (e.g. Painter's
    ``Resource``); the core never looks inside it.
    """

    url: str
    gui_name: str
    is_brush: bool = True
    handle: object = None


# -- creating -------------------------------------------------------------------


def versionless_url(url):
    """``resource://ctx/Name?version=abc.abr`` -> ``resource://ctx/Name``, percent-decoded."""
    base, _, query = url.partition("?")
    base = unquote(base)
    kept = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k != "version"]
    return f"{base}?{urlencode(kept)}" if kept else base


def resource_urls_from_drop(text):
    """The version-less ``resource://`` URLs of a ``text/uri-list`` drop, in order, each once."""
    if not isinstance(text, str):
        return []
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(RESOURCE_SCHEME):  # also skips "#" comments and other URLs
            continue
        url = versionless_url(line)
        if url not in urls:
            urls.append(url)
    return urls


def brush_button(resource):
    """The Layout's JSON for a new Brush button, without ``id`` and ``icon`` (see
    ``LayoutEditor.add_button``)."""
    return {"kind": "brush", "name": resource.gui_name, "resource": resource.url}


# -- the icon -------------------------------------------------------------------

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"  # the last chunk's type and CRC
_TOOLTIP_PNG = re.compile(r"data:image/png;base64,([A-Za-z0-9+/=]+)")


def png_from_tooltip(html):
    """The PNG embedded in an Assets tile's tooltip (``data:image/png;base64,…``), or ``None``."""
    if not isinstance(html, str):
        return None
    match = _TOOLTIP_PNG.search(html)
    if match is None:
        return None
    try:
        data = base64.b64decode(match.group(1), validate=True)
    except (binascii.Error, ValueError):
        return None
    return data if data.startswith(PNG_SIGNATURE) else None


def png_from_preset_file(path):
    """The first complete PNG inside a ``.sppr`` file, or ``None``. Other files are not searched."""
    if not path or Path(path).suffix.lower() != ".sppr":
        return None
    try:
        data = Path(path).read_bytes()
    except OSError:
        log.info("Could not read the preset file %s", path)
        return None
    start = data.find(PNG_SIGNATURE)
    if start < 0:
        return None
    end = data.find(PNG_END, start)
    if end < 0:
        return None
    return data[start : end + len(PNG_END)]


ICON_TOOLTIP = "tooltip"
ICON_DECORATION = "tile image"
ICON_PRESET_FILE = "preset file"
ICON_GENERIC = "generic"


def pick_brush_icon(tooltip_html, decoration_png, preset_path):
    """``(PNG bytes or None, source)``: the icon from the first source that has one:

    1. the PNG in the Assets tile's tooltip (256×256, sharp);
    2. the tile's ``DecorationRole`` image, already as PNG bytes (small);
    3. the PNG embedded in the ``.sppr`` file (``preset_path`` may be a function, called
       only if the first two have nothing).

    ``(None, ICON_GENERIC)`` means none had one: the Button gets the generic brush icon.
    """
    png = png_from_tooltip(tooltip_html)
    if png:
        return png, ICON_TOOLTIP
    if decoration_png:
        return decoration_png, ICON_DECORATION
    png = png_from_preset_file(preset_path() if callable(preset_path) else preset_path)
    if png:
        return png, ICON_PRESET_FILE
    return None, ICON_GENERIC


def brush_icon_png(tooltip_html, decoration_png, preset_path):
    """The PNG of ``pick_brush_icon``, or ``None`` for the generic icon."""
    return pick_brush_icon(tooltip_html, decoration_png, preset_path)[0]


def brush_icon(adapter, resource):
    """The icon PNG for a brush just dropped, or ``None`` (the generic icon). The preset
    file is looked up only when the Assets window has no image for it."""

    def preset_path():
        try:
            return adapter.resource_file_path(resource)
        except Exception:
            log.exception("Could not find the file of %r", resource.url)
            return None

    try:
        tooltip, decoration = adapter.assets_icon_sources(resource)
    except Exception:
        log.exception("Could not read the Assets tile of %r", resource.url)
        tooltip, decoration = None, None
    png, source = pick_brush_icon(tooltip, decoration, preset_path)
    log.info("Icon of %r: %s", resource.url, source)  # 11.1 check: which presets fall back
    return png


# -- activating -----------------------------------------------------------------

WAITING = "waiting"
DONE = "done"
TIMED_OUT = "timed out"
FAILED = "failed"
MISSING = "missing"

POLL_MS = 30
TIMEOUT_MS = 4000


def _now_ms():
    return time.monotonic() * 1000


class BrushActivation:
    """Makes a resolved brush the active one, as a state machine polled on a timer.

    ``start``: open and raise the Assets window, then ``show_in_ui``. ``poll`` (every
    ``POLL_MS``): look for the tile; once it is in the same place twice in a row (the
    view has stopped scrolling), click its centre. Gives up after ``timeout_ms``.

    The adapter provides ``open_assets() -> bool``, ``show_in_ui(resource)``,
    ``tile_rect(gui_name) -> (x, y, w, h) or None`` and ``click_tile(rect)``.
    """

    def __init__(self, adapter, resource, now=None, timeout_ms=TIMEOUT_MS):
        self.adapter = adapter
        self.resource = resource
        self.now = now or _now_ms
        self.timeout_ms = timeout_ms
        self.state = WAITING
        self.message = None
        self._started = None
        self._last_rect = None

    def _end(self, state, message=None):
        self.state, self.message = state, message
        if message:
            log.warning("Activating %r: %s", self.resource.url, message)
        return state

    def start(self):
        self._started = self.now()
        try:
            opened = self.adapter.open_assets()
        except Exception:
            log.exception("Opening the Assets window failed")
            opened = False
        if not opened:
            return self._end(FAILED, "The Assets window could not be found.")
        try:
            self.adapter.show_in_ui(self.resource)
        except Exception:  # the poll may still find the tile
            log.exception("show_in_ui failed for %r", self.resource.url)
        return self.state

    def poll(self):
        if self.state != WAITING:
            return self.state
        if self.now() - self._started > self.timeout_ms:
            seconds = round(self.timeout_ms / 1000)
            return self._end(
                TIMED_OUT, f"“{self.resource.gui_name}” did not appear in the Assets window within {seconds} seconds."
            )
        try:
            rect = self.adapter.tile_rect(self.resource.gui_name)
        except Exception:
            log.debug("Looking for the tile failed; trying again", exc_info=True)
            rect = None
        if rect is None or rect != self._last_rect:
            self._last_rect = rect
            return self.state
        try:
            self.adapter.click_tile(rect)
        except Exception:
            log.exception("Clicking the tile failed")
            return self._end(FAILED, f"“{self.resource.gui_name}” could not be clicked in the Assets window.")
        log.info("Activated %r", self.resource.url)
        return self._end(DONE)


@dataclass(frozen=True)
class StepResult:
    state: str  # DONE, TIMED_OUT, FAILED or MISSING
    message: str = None

    @property
    def ok(self):
        return self.state == DONE


def missing_message(url):
    return f"This brush is not available on this machine: {url}"


def resolve(adapter, url):
    """The brush behind ``url`` on this machine, or ``None`` if it is missing."""
    try:
        return adapter.resolve_resource(url)
    except Exception:
        log.exception("Looking up %r failed", url)
        return None


class _Running:
    """A ``select_brush`` in progress: its timer, and ``cancel``."""

    def __init__(self, adapter, activation, done):
        self.activation = activation
        self._done = done
        self.timer = adapter.repeat(POLL_MS, self._tick)

    def _tick(self):
        if self._done is None:
            return
        if self.activation.poll() != WAITING:
            self._finish()

    def _finish(self):
        done, self._done = self._done, None
        self.timer.stop()
        done(StepResult(self.activation.state, self.activation.message))

    def cancel(self):
        self._done = None
        self.timer.stop()


def select_brush(adapter, step, done, now=None):
    """Run a ``select_brush`` Step: ``done(StepResult)`` is called exactly once, maybe
    before this returns. Returns a handle with ``cancel()`` while it is still polling,
    else ``None``."""
    url = step["resource"]
    resource = resolve(adapter, url)
    if resource is None:
        done(StepResult(MISSING, missing_message(url)))
        return None
    activation = BrushActivation(adapter, resource, now)
    if activation.start() != WAITING:
        done(StepResult(activation.state, activation.message))
        return None
    return _Running(adapter, activation, done)
