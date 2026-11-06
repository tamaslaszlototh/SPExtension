# PROTOTYPE – eldobható kód, nem kerül a main ágra.
# A Workflow és a Step-ek adatmodellje: v1 Step-katalógus (Grilling: a v1 Step-katalógus, #7),
# sorrendszabály (UI Step csak a végén), Step-ikonok és a Workflow button ikonjának három stratégiája.

import copy
import itertools

from PySide6 import QtCore, QtGui

Qt = QtCore.Qt
_ids = itertools.count(1)

LAYER, UI = "layer", "ui"

# kulcs -> (rövid név, zóna, kategória, ikon-felirat)
CATALOG = {
    "fill":           ("Fill layer", LAYER, "layer", "F"),
    "paint":          ("Paint layer", LAYER, "layer", "P"),
    "folder":         ("Folder", LAYER, "layer", "D"),
    "mask":           ("Maszk", LAYER, "mask", "M"),
    "generator":      ("Generator", LAYER, "effect", "G"),
    "filter":         ("Filter", LAYER, "effect", "Fx"),
    "levels":         ("Levels", LAYER, "effect", "Lv"),
    "anchor":         ("Anchor point", LAYER, "effect", "A"),
    "blend":          ("Blend mode", LAYER, "setting", "B"),
    "opacity":        ("Opacity", LAYER, "setting", "%"),
    "smart_material": ("Smart material", LAYER, "smart", "SM"),
    "smart_mask":     ("Smart mask", LAYER, "smart", "Sk"),
    "brush":          ("Brush", UI, "ui", "Br"),
    "menu":           ("Menüparancs", UI, "ui", "≡"),
    "save":           ("Mentés", UI, "ui", "S"),
}

# a „+ Step” menü csoportjai
MENU_GROUPS = [
    ("Layer", ["fill", "paint", "folder"]),
    ("Maszk", ["mask"]),
    ("Effekt", ["generator", "filter", "levels", "anchor"]),
    ("Beállítás", ["blend", "opacity"]),
    ("Smart", ["smart_material", "smart_mask"]),
    ("A végén (UI)", ["brush", "menu", "save"]),
]

CAT_COLOR = {"layer": "#3d7bd9", "mask": "#7a7a7a", "effect": "#8e5bd0", "setting": "#2a9d8f",
             "smart": "#d9822b", "ui": "#3f9d4a"}

BLEND_MODES = ["Normal", "Multiply", "Screen", "Overlay", "Linear Dodge", "Subtract", "Darken", "Lighten",
               "Color Burn", "Color Dodge", "Soft Light", "Passthrough"]
CHANNELS = ["BaseColor", "Roughness", "Metallic", "Height", "Normal", "Opacity", "Emissive"]


def zone(step):
    return CATALOG[step["type"]][1]


def new_step(kind, src="kézi", **params):
    defaults = {
        "fill": {"name": ""}, "paint": {"name": ""}, "folder": {"name": ""},
        "mask": {"bg": "Black"},
        "generator": {"resource": None, "target": "mask"}, "filter": {"resource": None, "target": "layer"},
        "levels": {"target": "layer"}, "anchor": {"target": "layer"},
        "blend": {"mode": "Multiply"}, "opacity": {"value": 50, "channels": ["BaseColor"]},
        "smart_material": {"resource": None}, "smart_mask": {"resource": None},
        "brush": {"resource": None}, "menu": {"action": None}, "save": {},
    }[kind]
    p = copy.deepcopy(defaults)
    p.update(params)
    return {"id": next(_ids), "type": kind, "params": p, "src": src}


def _copy(obj):
    """Mély másolat, de a _-al kezdődő kulcsok (QIcon, QAction) értékét hivatkozásként viszi át."""
    if isinstance(obj, dict):
        return {k: (v if k.startswith("_") else _copy(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_copy(v) for v in obj]
    return obj


def clone_steps(steps):
    out = []
    for s in steps:
        c = _copy({k: v for k, v in s.items() if not k.startswith("_")})
        c["id"] = next(_ids)
        out.append(c)
    return out


def _res_name(r):
    return r["name"] if r else None


def missing(step):
    """Ha a Step-ből hiányzik valami, ami nélkül nem futhat: rövid üzenet, különben None."""
    t, p = step["type"], step["params"]
    if t in ("generator", "filter", "smart_material", "smart_mask", "brush") and not p.get("resource"):
        return "resource kiválasztandó"
    if t == "menu" and not p.get("action"):
        return "parancs kiválasztandó"
    if t == "opacity" and not p.get("channels"):
        return "legalább egy csatorna kell"
    return None


def label(step):
    t, p = step["type"], step["params"]
    if t in ("fill", "paint", "folder"):
        base = CATALOG[t][0] + " hozzáadása"
        return base + (f" „{p['name']}”" if p.get("name") else "")
    if t == "mask":
        return "Fekete maszk" if p["bg"] == "Black" else "Fehér maszk"
    tgt = " (maszkra)" if p.get("target") == "mask" else " (layerre)"
    if t in ("generator", "filter"):
        return f"{CATALOG[t][0]}: {_res_name(p['resource']) or '⚠ ?'}{tgt}"
    if t in ("levels", "anchor"):
        return CATALOG[t][0] + tgt
    if t == "blend":
        return f"Blend: {p['mode']}"
    if t == "opacity":
        ch = p["channels"]
        chs = "minden csatorna" if len(ch) >= len(CHANNELS) else ", ".join(ch)
        return f"Opacity {p['value']}% ({chs})"
    if t in ("smart_material", "smart_mask", "brush"):
        return f"{CATALOG[t][0]}: {_res_name(p['resource']) or '⚠ kiválasztandó'}"
    if t == "menu":
        a = p.get("action")
        return f"Menü: {a['path'] if a else '⚠ kiválasztandó'}"
    return "Mentés (Save)"


def short(step):
    """Csempe/csip felirat: egy-két szó."""
    t, p = step["type"], step["params"]
    if t == "mask":
        return "Fekete maszk" if p["bg"] == "Black" else "Fehér maszk"
    if t in ("generator", "filter", "smart_material", "smart_mask", "brush"):
        return _res_name(p["resource"]) or ("⚠ " + CATALOG[t][0])
    if t == "menu":
        a = p.get("action")
        return a["text"] if a else "⚠ Menü"
    if t == "blend":
        return p["mode"]
    if t == "opacity":
        return f"Opacity {p['value']}%"
    if t in ("fill", "paint", "folder") and p.get("name"):
        return p["name"]
    return CATALOG[t][0]


def auto_name(steps):
    parts = [short(s) for s in steps[:3]]
    return " + ".join(parts) if parts else "Új Workflow"


# ---------------------------------------------------------------- sorrend

def normalize(steps):
    """Layer Step-ek elöl, UI Step-ek a végén (stabil). Visszaadja az új listát és a hátrébb tett UI Step-eket."""
    layer = [s for s in steps if zone(s) == LAYER]
    ui = [s for s in steps if zone(s) == UI]
    moved = []
    seen_layer_after = False
    for s in reversed(steps):
        if zone(s) == LAYER:
            seen_layer_after = True
        elif seen_layer_after:
            moved.append(s)
    return layer + ui, moved


def insert_step(steps, step):
    """Kézi hozzáadás: layer Step a layer-rész végére, UI Step a lista végére."""
    if zone(step) == UI:
        steps.append(step)
    else:
        i = sum(1 for s in steps if zone(s) == LAYER)
        steps.insert(i, step)


def can_move(steps, i, j):
    return 0 <= j < len(steps) and zone(steps[i]) == zone(steps[j])


# ---------------------------------------------------------------- ikonok

def _rounded(p, rect, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(color))
    p.drawRoundedRect(rect, rect.width() * 0.18, rect.width() * 0.18)


def _text(p, rect, txt, px):
    p.setPen(QtGui.QColor(255, 255, 255, 235))
    f = p.font()
    f.setPixelSize(max(6, int(px)))
    f.setBold(True)
    p.setFont(f)
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)


def step_pixmap(step, size=48, action_icon=None):
    """A „csomagolt saját ikonkészlet” helyettesítője: kategóriaszín + rövid jel.
    Menüparancsnál a Painter QAction ikonja, ha van (#7: menüparancsnál QAction.icon())."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    t = step["type"]
    r = QtCore.QRectF(1, 1, size - 2, size - 2)
    icon = action_icon
    if t == "menu" and icon is None:
        a = step["params"].get("action")
        icon = a.get("_icon") if a else None
    if t == "menu" and icon is not None and not icon.isNull():
        _rounded(p, r, "#2c2c2c")
        icon.paint(p, r.adjusted(size * 0.12, size * 0.12, -size * 0.12, -size * 0.12).toRect())
    elif t == "brush":
        h = (sum(ord(c) for c in (short(step))) * 37) % 360
        g = QtGui.QRadialGradient(size * 0.4, size * 0.38, size * 0.5)
        g.setColorAt(0, QtGui.QColor.fromHsv(h, 60, 255))
        g.setColorAt(0.6, QtGui.QColor.fromHsv(h, 200, 200))
        g.setColorAt(1, QtGui.QColor.fromHsv(h, 220, 70))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(r.adjusted(size * 0.06, size * 0.06, -size * 0.06, -size * 0.06))
    elif t == "mask":
        _rounded(p, r, "#555")
        black = step["params"]["bg"] == "Black"
        p.setBrush(QtGui.QColor("#111" if black else "#f2f2f2"))
        p.drawEllipse(r.adjusted(size * 0.2, size * 0.2, -size * 0.2, -size * 0.2))
    else:
        _rounded(p, r, CAT_COLOR[CATALOG[t][2]])
        _text(p, r, CATALOG[t][3], size * (0.42 if len(CATALOG[t][3]) == 1 else 0.34))
    if missing(step):
        p.setBrush(QtGui.QColor("#e0a800"))
        p.setPen(QtGui.QPen(QtGui.QColor("#222"), 1))
        d = size * 0.36
        p.drawEllipse(QtCore.QRectF(size - d - 1, 1, d, d))
        _text(p, QtCore.QRectF(size - d - 1, 1, d, d), "!", d * 0.8)
    p.end()
    return pm


def step_icon(step, size=48):
    return QtGui.QIcon(step_pixmap(step, size))


# A Workflow button ikonja: három automatikus stratégia (nincs kézi ikonválasztás, lásd a térkép Notes-át).
ICON_STRATEGY = {"A": "first", "B": "grid", "C": "main_badge"}
ICON_STRATEGY_HU = {"first": "az első Step ikonja", "grid": "2×2 az első négy Step ikonjából",
                    "main_badge": "a fő Step ikonja + Step-szám"}


def main_step(steps):
    for s in steps:
        if s["type"] in ("fill", "paint", "folder", "smart_material"):
            return s
    return steps[0] if steps else None


def workflow_icon(steps, strategy, size=64):
    pm = QtGui.QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    if not steps:
        return QtGui.QIcon(pm)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    if strategy == "first":
        p.drawPixmap(0, 0, step_pixmap(steps[0], size))
    elif strategy == "grid":
        h = size // 2
        for k, s in enumerate(steps[:4]):
            p.drawPixmap((k % 2) * h, (k // 2) * h, step_pixmap(s, h - 1))
    else:
        p.drawPixmap(0, 0, step_pixmap(main_step(steps), size))
        d = size * 0.46
        rr = QtCore.QRectF(size - d, size - d, d, d)
        p.setBrush(QtGui.QColor("#f5f5f5"))
        p.setPen(QtGui.QPen(QtGui.QColor("#202020"), 2))
        p.drawEllipse(rr)
        p.setPen(QtGui.QColor("#202020"))
        f = p.font()
        f.setPixelSize(int(d * 0.62))
        f.setBold(True)
        p.setFont(f)
        p.drawText(rr, Qt.AlignmentFlag.AlignCenter, str(len(steps)))
    p.end()
    return QtGui.QIcon(pm)


def clean(obj):
    """JSON-nézet: a _-al kezdődő kulcsok (pl. QIcon, QAction) nélkül."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj
