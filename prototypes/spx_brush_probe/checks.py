# PROTOTYPE – eldobható kód, nem kerül a main ágra.
# A „Prototype: Brush button aktiválás és ikon a hivatalos API hiányában” ticket próbái.
# Riportok: %APPDATA%\spx_brush_probe\
#
# Jelöltek:
#   A  Resource.show_in_ui()               – hivatalos, csak kijelöl (v3.7 óta nincs gombja: kizárva)
#   B  substance_painter.js.evaluate()     – legacy JS API felderítése és a talált függvények kipróbálása
#   C  Qt/QML UI-automatizálás             – kattintás szimulálása az Assets ablak elemén
#   T2 thumbnail a preset fájlból / cache-ből
#   T3 thumbnail képernyőképből / QML Image elemből
#   T4 thumbnail az Assets nézet modelljéből (DecorationRole) és widget-grabből (v3.5)
#   T5 a %APPDATA%\...\previews gyorsítótár formátuma (v3.5)

import io, os, re, sys, json, time, zipfile, traceback, importlib

from PySide6 import QtCore, QtGui, QtWidgets

import substance_painter.resource as res
import substance_painter.ui as ui

PROBE_VERSION = "v3.7"
REPORT_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "spx_brush_probe")
OUT = io.StringIO()
_JS_API = {}        # felderített JS névtér: {"alg.x.y": "function/1", ...}
_FILE_INDEX = None  # {kisbetűs fájlnév törzs: [útvonalak]}
_DOC_DIRS = []


# ----------------------------------------------------------------- segédek
def log(*a):
    print(*a, file=OUT)


def section(title):
    log("")
    log("=" * 70)
    log(title)
    log("=" * 70)


def guard(fn, *args):
    try:
        return fn(*args)
    except Exception:
        log("!! KIVÉTEL:")
        log(traceback.format_exc())


def painter_version():
    try:
        import substance_painter.application as app
        return app.version()
    except Exception:
        return "unknown"


def flush():
    """A pufferelt sorokat a verziós riportfájlhoz fűzi, és visszaadja az útvonalát."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"brush_{painter_version()}.txt")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(OUT.getvalue())
    OUT.seek(0)
    OUT.truncate()
    return path


def out_file(name):
    os.makedirs(REPORT_DIR, exist_ok=True)
    return os.path.join(REPORT_DIR, f"{painter_version()}_{name}")


def wait(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.02)


def ask(parent, question):
    """Igen / Nem / Nem tudom kérdés a barátnak. A válasz a riportba kerül."""
    box = QtWidgets.QMessageBox(parent)
    box.setWindowTitle("SPX Brush Probe – kérdés")
    box.setText(question)
    yes = box.addButton("Igen", QtWidgets.QMessageBox.ButtonRole.YesRole)
    no = box.addButton("Nem", QtWidgets.QMessageBox.ButtonRole.NoRole)
    box.addButton("Nem tudom", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    box.exec()
    ans = "IGEN" if box.clickedButton() is yes else "NEM" if box.clickedButton() is no else "NEM TUDOM"
    log(f"  >> KÉRDÉS: {question}\n  >> VÁLASZ: {ans}")
    return ans


def ask_text(parent, question):
    text, ok = QtWidgets.QInputDialog.getMultiLineText(parent, "SPX Brush Probe – vélemény", question)
    log(f"  >> KÉRDÉS: {question}\n  >> VÁLASZ: {text if ok else '(kihagyva)'}")


def wait_for_user(parent, text, button="Kész"):
    """Nem modális ablak: közben a Painterben lehet kattintani."""
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("SPX Brush Probe – teendő")
    dlg.setWindowModality(QtCore.Qt.WindowModality.NonModal)
    dlg.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    lay = QtWidgets.QVBoxLayout(dlg)
    lab = QtWidgets.QLabel(text)
    lab.setWordWrap(True)
    lay.addWidget(lab)
    b = QtWidgets.QPushButton(button)
    lay.addWidget(b)
    done = []
    b.clicked.connect(lambda: done.append(1))
    dlg.show()
    while not done and dlg.isVisible():
        QtWidgets.QApplication.processEvents()
        time.sleep(0.03)
    dlg.close()


PAINT_CHECK = ("Ellenőrzés: fess egy rövid vonást a modellre.\n"
               "Olyan mintát fest, mint a(z) „{name}” brush (az Assets ablakban látható ikonja alapján)?\n"
               "(Utána Ctrl+Z-vel visszavonhatod a vonást.)")


def main_window():
    return ui.get_main_window()


_SB = []


def _shiboken():
    if not _SB:
        mod = None
        for name in ("shiboken6", "PySide6.shiboken6"):
            try:
                mod = importlib.import_module(name)
                break
            except Exception:
                pass
        _SB.append(mod)
    return _SB[0]


def alive(o):
    """False, ha a Python wrapper mögötti C++ objektum már törölve van (11.1 „ghost widget”)."""
    sb = _shiboken()
    if sb is not None:
        try:
            if not sb.isValid(o):
                return False
        except Exception:
            pass
    try:
        o.objectName()
        return True
    except RuntimeError:
        return False


def live_children(parent, cls):
    """parent alatti cls példányok. Csak QApplication.allWidgets(): 11.1-en a findChildren halott
    wrappereket ad, és a hívása a már élő wrappereket is érvénytelenítheti, ezért kerüljük."""
    out = []
    for c in QtWidgets.QApplication.allWidgets():
        try:
            if not isinstance(c, cls) or not alive(c):
                continue
            if c is not parent and not _descends(c, parent):
                continue
        except RuntimeError:
            continue
        out.append(c)
    return out


def _descends(w, parent):
    """Szülőlánc bejárása (az isAncestorOf megáll az ablakhatáron, pl. lebegő docknál)."""
    def key(o):
        sb = _shiboken()
        try:
            return sb.getCppPointer(o)[0] if sb else id(o)
        except Exception:
            return id(o)
    target = key(parent)
    p = w.parentWidget()
    while p is not None:
        if p is parent or key(p) == target:
            return True
        p = p.parentWidget()
    return False


_DOCK_DIAG = []


def _dock_diagnostics():
    if _DOCK_DIAG:
        return
    _DOCK_DIAG.append(1)
    sb = _shiboken()
    items = [w for w in QtWidgets.QApplication.allWidgets() if isinstance(w, QtWidgets.QDockWidget)]
    log(f"  dock-diagnosztika: shiboken={getattr(sb, '__name__', None)}, allWidgets: {len(items)} dock, "
        f"élő {sum(1 for d in items if alive(d))} (findChildren-t nem hívunk)")


def find_dock(object_name, title_part):
    _dock_diagnostics()
    found = []
    for d in QtWidgets.QApplication.allWidgets():
        try:
            if not isinstance(d, QtWidgets.QDockWidget):
                continue
            found.append((d, d.objectName(), d.windowTitle()))
        except RuntimeError:
            continue
    for d, name, _ in found:
        if name == object_name:
            return d
    for d, _, title in found:
        if title_part.lower() in title.lower():
            return d
    log(f"  {title_part} dock nem található; dockok: {[(n, t) for _, n, t in found]}")
    return None


def assets_dock():
    return find_dock("NewShelf", "Assets")


def props_dock():
    return find_dock("Tool", "Properties")


def global_rect(w):
    return QtCore.QRect(w.mapToGlobal(QtCore.QPoint(0, 0)), w.size())


# ----------------------------------------------------------------- presetek
def _usages(r):
    try:
        return list(r.usages())
    except Exception:
        return []


def list_presets():
    """(címke, Resource) párok: előbb a tool presetek, utána a brush (alpha) resource-ok."""
    section(f"0. Presetek listázása – próba-verzió {PROBE_VERSION}, {time.strftime('%Y-%m-%d %H:%M:%S')}")
    found = {}
    for q in ("u:tool", "u:brush", ""):
        try:
            rs = res.search(q)
        except Exception as e:
            log(f"  search({q!r}) HIBA: {e}")
            continue
        log(f"  search({q!r}) -> {len(rs)} találat")
        for r in rs:
            us = _usages(r)
            kind = "TOOL" if res.Usage.TOOL in us else "BRUSH" if res.Usage.BRUSH in us else None
            if kind is None:
                continue
            try:
                url = r.identifier().url()
            except Exception:
                continue
            found.setdefault(url, (kind, r))
    items = []
    for url, (kind, r) in found.items():
        try:
            name = r.gui_name()
        except Exception:
            name = url
        items.append((f"{name}  [{kind}]  {url}", kind, r))
    items.sort(key=lambda t: (t[1] != "TOOL", t[0].lower()))
    log(f"  összesen {len(items)} preset (TOOL: {sum(1 for t in items if t[1] == 'TOOL')})")
    for label, _, _ in items[:40]:
        log("   ", label)
    return [(label, r) for label, _, r in items]


def describe_resource(r):
    log("  Resource részletek:")
    rid = r.identifier()
    log(f"    url={rid.url()} context={rid.context!r} name={rid.name!r} version={rid.version!r}")
    for m in ("gui_name", "type", "usages", "tags", "category", "location"):
        if hasattr(r, m):
            log(f"    {m}() = {guard(getattr(r, m))!r}")
    public = [n for n in dir(r) if not n.startswith("_")]
    log(f"    dir(): {public}")
    for n in public:
        if re.search(r"preview|thumb|path|file|icon|image", n, re.I):
            try:
                log(f"    {n}() = {getattr(r, n)()!r}")
            except Exception as e:
                log(f"    {n}() -> {type(e).__name__}: {e}")


# ----------------------------------------------------------------- UI fa / QML
def _qml_props(obj):
    mo = obj.metaObject()
    props = {}
    for p in ("text", "name", "title", "label", "source", "toolTip", "resourceName",
              "url", "selected", "isCurrentItem", "current", "checked"):
        if mo.indexOfProperty(p) >= 0:
            try:
                v = obj.property(p)
            except Exception:
                continue
            if v not in (None, "", False):
                props[p] = str(v.toString() if hasattr(v, "toString") else v)[:100]
    return props


def qml_items(root, limit=6000):
    """(mélység, item, osztály, props) lista a QML fából."""
    out = []

    def walk(item, depth):
        if len(out) >= limit:
            return
        out.append((depth, item, item.metaObject().className(), _qml_props(item)))
        for c in item.childItems():
            walk(c, depth + 1)

    walk(root, 0)
    return out


def quick_surfaces(region=None):
    """Minden QML felület: (név, item-gyökér, eseménycél, scene->global függvény).
    region: QRect globális koordinátákban; csak az ezzel átfedőket adja vissza."""
    surfaces = []
    try:
        from PySide6 import QtQuickWidgets
        for qw in live_children(main_window(), QtQuickWidgets.QQuickWidget):
            root = qw.rootObject()
            if root is None or not qw.isVisible():
                continue
            if region is not None and not global_rect(qw).intersects(region):
                continue
            surfaces.append((f"QQuickWidget '{qw.objectName()}' {qw.source().toString()}", root, qw,
                             lambda p, qw=qw: qw.mapToGlobal(p.toPoint())))
    except Exception as e:
        log("  QQuickWidget bejárás hiba:", e)
    try:
        from PySide6 import QtQuick
        for win in QtGui.QGuiApplication.allWindows():
            if not isinstance(win, QtQuick.QQuickWindow) or not win.isVisible():
                continue
            g = QtCore.QRect(win.mapToGlobal(QtCore.QPoint(0, 0)), win.size())
            if region is not None and not g.intersects(region):
                continue
            surfaces.append((f"QQuickWindow '{win.objectName()}' {g}", win.contentItem(), win,
                             lambda p, win=win: win.mapToGlobal(p.toPoint())))
    except Exception as e:
        log("  QQuickWindow bejárás hiba:", e)
    return surfaces


def _child_map():
    """{szülő C++ pointer: [gyerek widgetek]} az allWidgets()-ből (children()/findChildren nélkül)."""
    sb, m = _shiboken(), {}
    for c in QtWidgets.QApplication.allWidgets():
        try:
            p = c.parentWidget()
            if p is None:
                continue
            k = sb.getCppPointer(p)[0] if sb else id(p)
        except Exception:
            continue
        m.setdefault(k, []).append(c)
    return m


def dump_widget_tree(w, depth=0, maxd=12, lines=None, cmap=None):
    lines = [] if lines is None else lines
    cmap = _child_map() if cmap is None else cmap
    if depth > maxd or len(lines) > 3000:
        return lines
    extra = ""
    for attr in ("text", "windowTitle", "toolTip"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                v = f()
                if v:
                    extra += f" {attr}={v[:60]!r}"
            except Exception:
                pass
    if isinstance(w, QtWidgets.QAbstractItemView) and w.model() is not None:
        m = w.model()
        sample = [str(m.index(i, 0).data()) for i in range(min(8, m.rowCount()))]
        extra += f" MODEL rows={m.rowCount()} cols={m.columnCount(QtCore.QModelIndex())} minta={sample}"
    lines.append("  " * depth + f"{w.metaObject().className()} '{w.objectName()}' "
                 f"vis={w.isVisible()} {w.width()}x{w.height()}{extra}")
    sb = _shiboken()
    try:
        k = sb.getCppPointer(w)[0] if sb else id(w)
    except Exception:
        return lines
    for c in cmap.get(k, []):
        if alive(c):
            dump_widget_tree(c, depth + 1, maxd, lines, cmap)
    return lines


def collect_texts(dock):
    """A dock összes látható szövege (widgetek + átfedő QML felületek), az előtte/utána diffhez."""
    texts = set()
    if dock is None:
        return texts
    for w in [dock] + live_children(dock, QtWidgets.QWidget):
        for attr in ("text", "currentText", "toolTip"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    v = f()
                    if isinstance(v, str) and v.strip():
                        texts.add(v.strip()[:80])
                except Exception:
                    pass
    for _, root, _, _ in quick_surfaces(global_rect(dock)):
        for _, item, _, props in qml_items(root, limit=4000):
            for k in ("text", "name", "title", "label", "source"):
                if k in props:
                    texts.add(f"{k}:{props[k]}")
    return texts


def log_diff(before, after, label):
    added, removed = sorted(after - before), sorted(before - after)
    log(f"  [{label}] Properties szövegek változása: +{len(added)} / -{len(removed)}")
    for t in added[:40]:
        log("     +", t)
    for t in removed[:40]:
        log("     -", t)
    return bool(added or removed)


def screenshot(widget, name):
    if widget is None:
        return None
    try:
        g = global_rect(widget)
        scr = QtGui.QGuiApplication.screenAt(g.center()) or QtGui.QGuiApplication.primaryScreen()
        geo = scr.geometry()
        pix = scr.grabWindow(0, g.x() - geo.x(), g.y() - geo.y(), g.width(), g.height())
        path = out_file(name)
        pix.save(path)
        log(f"  képernyőkép: {path} ({pix.width()}x{pix.height()})")
        return path
    except Exception as e:
        log(f"  képernyőkép hiba ({name}): {e}")


# ----------------------------------------------------------------- 1. felderítés
JS_WALK = r"""(function(){
var out = {}, n = 0;
function names(o){ var s = {};
  try { for (var k in o) s[k] = 1; } catch(e) {}
  try { Object.getOwnPropertyNames(o).forEach(function(k){ s[k] = 1; }); } catch(e) {}
  return Object.keys(s); }
function walk(o, p, d){
  if (d > 4 || n > 6000) return;
  names(o).forEach(function(k){
    if (k === 'prototype' || k === 'constructor' || k.indexOf('__') === 0) return;
    n++; var v;
    try { v = o[k]; } catch(e) { out[p + k] = 'ERR'; return; }
    var t = typeof v;
    if (t === 'function') out[p + k] = 'function/' + v.length;
    else if (t === 'object' && v !== null) { out[p + k] = 'object'; walk(v, p + k + '.', d + 1); }
    else out[p + k] = t + ': ' + String(v).slice(0, 80);
  });
}
walk(alg, 'alg.', 0);
return JSON.stringify(out);
})()"""

INTERESTING = re.compile(r"tool|brush|preset|resource|shelf|thumb|preview|icon", re.I)


def js_discovery():
    section("1a. JS API felderítése (substance_painter.js)")
    import substance_painter.js as js
    log("  js modul:", [n for n in dir(js) if not n.startswith("_")])
    try:
        log("  globális nevek:", js.evaluate("JSON.stringify(Object.getOwnPropertyNames(this))"))
    except Exception as e:
        log("  globális nevek HIBA:", e)
    raw = js.evaluate(JS_WALK)
    api = json.loads(raw) if isinstance(raw, str) else dict(raw)
    _JS_API.clear()
    _JS_API.update(api)
    path = out_file("js_api.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(api, fh, indent=1, ensure_ascii=False, sort_keys=True)
    log(f"  {len(api)} név, teljes lista: {path}")
    top = sorted({k.split(".")[1] for k in api if k.count(".") >= 1})
    log("  alg névterek:", top)
    log("  érdekes nevek (tool|brush|preset|resource|shelf|thumb|preview|icon):")
    for k in sorted(api):
        if INTERESTING.search(k):
            log(f"    {k} = {api[k]}")


def _roots():
    roots = []
    try:
        import substance_painter_plugins
        for p in substance_painter_plugins.path:
            p = os.path.normpath(p)
            if p.lower().endswith(os.path.join("resources", "python")):
                roots.append(("install", os.path.dirname(os.path.dirname(p))))
    except Exception as e:
        log("  install mappa nem található:", e)
    docs = os.path.join(os.path.expanduser("~"), "Documents", "Adobe", "Adobe Substance 3D Painter")
    roots.append(("documents", docs))
    for env in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(env)
        if base:
            roots.append((env, os.path.join(base, "Adobe", "Adobe Substance 3D Painter")))
    return roots


def build_file_index():
    global _FILE_INDEX
    if _FILE_INDEX is not None:
        return _FILE_INDEX, _DOC_DIRS
    _FILE_INDEX = {}
    doc_dirs = _DOC_DIRS
    doc_dirs.clear()
    for label, root in _roots():
        if not os.path.isdir(root):
            log(f"  [{label}] nincs: {root}")
            continue
        n, exts, t0 = 0, {}, time.time()
        for dp, dns, fns in os.walk(root):
            low = dp.lower()
            if re.search(r"javascript|scripting|[\\/]doc", low) and any(f.lower().endswith((".html", ".htm", ".js")) for f in fns):
                doc_dirs.append(dp)
            for f in fns:
                n += 1
                stem, ext = os.path.splitext(f)
                exts[ext.lower()] = exts.get(ext.lower(), 0) + 1
                _FILE_INDEX.setdefault(stem.lower(), []).append(os.path.join(dp, f))
            if time.time() - t0 > 40:
                log(f"  [{label}] időkorlát, részleges index")
                break
        top = sorted(exts.items(), key=lambda kv: -kv[1])[:15]
        log(f"  [{label}] {root}: {n} fájl, kiterjesztések: {top}")
    return _FILE_INDEX, doc_dirs


def js_docs():
    section("1b. JS API dokumentáció a telepítésben + fájlindex")
    _, doc_dirs = build_file_index()
    # csak a legfelső doksi-mappák
    tops = [d for d in doc_dirs if not any(d != o and d.startswith(o + os.sep) for o in doc_dirs)]
    log("  doksi-mappák:", tops)
    hits = {}
    zpath = out_file("js_doc.zip")
    total = 0
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for top in tops:
            if "python" in top.lower():
                continue
            for dp, _, fns in os.walk(top):
                for f in fns:
                    p = os.path.join(dp, f)
                    total += os.path.getsize(p)
                    if total < 40 * 1024 * 1024:
                        z.write(p, os.path.relpath(p, os.path.dirname(top)))
                    if f.lower().endswith((".html", ".htm", ".js")):
                        try:
                            txt = open(p, encoding="utf-8", errors="ignore").read()
                        except Exception:
                            continue
                        for m in re.finditer(r"alg\.[A-Za-z_.]*(?:tool|brush|preset|shelf|resource|thumb|preview)[A-Za-z_]*", txt, re.I):
                            hits[m.group(0)] = hits.get(m.group(0), 0) + 1
    log(f"  doksi zip: {zpath} ({total // 1024} KB forrás)")
    log("  doksiban talált érdekes alg.* nevek:")
    for k in sorted(hits):
        log(f"    {k}  (x{hits[k]})")


def ui_structure():
    section("1c. Assets és Properties ablak felépítése (widget- és QML-fa)")
    for label, dock in (("Assets", assets_dock()), ("Properties", props_dock())):
        if dock is None:
            log(f"  {label} dock nem található")
            continue
        log(f"  --- {label}: objectName={dock.objectName()!r} title={dock.windowTitle()!r} "
            f"visible={dock.isVisible()} rect={global_rect(dock)}")
        for line in dump_widget_tree(dock, maxd=10):
            log("   ", line)
        for name, root, _, _ in quick_surfaces(global_rect(dock) if dock.isVisible() else None):
            items = qml_items(root, limit=3000)
            log(f"    QML felület: {name}: {len(items)} item")
            for depth, _, cls, props in items[:400]:
                if props or depth < 5:
                    log("     " + "  " * min(depth, 20) + f"{cls} {props if props else ''}")
    log("  QtTest elérhető:", _qtest() is not None)


def api_presence():
    section("1d. Hivatalos API-k megléte ebben a verzióban")
    for owner, names in ((res.Resource, ("show_in_ui", "set_custom_preview", "reset_preview")),
                         (res, ("show_resources_in_ui", "Shelves", "Shelf", "import_session_resource",
                                "import_project_resource"))):
        for n in names:
            log(f"  {getattr(owner, '__name__', owner)}.{n}: {'VAN' if hasattr(owner, n) else 'NINCS'}")
    for cls_name, names in (("Shelves", ("add", "all", "remove")), ("Shelf", ("import_resource", "path", "name"))):
        cls = getattr(res, cls_name, None)
        if cls is not None:
            log(f"  {cls_name}: {[n for n in dir(cls) if not n.startswith('_')]}")


QML_HANDLER = re.compile(r"on(Clicked|DoubleClicked|Activated|Pressed|Released|Dropped)\b|"
                         r"\b\w+\.(set|select|activate|apply|use|load)\w*(Tool|Brush|Preset|Resource)\w*\s*\(", re.I)
QML_TOPIC = re.compile(r"tool|brush|preset|shelf|asset|resource", re.I)


def qml_sources():
    """A telepítés .qml/.js forrásai zipben, és a preset-kattintás kezelőinek gyors listája."""
    section("1e. A Painter saját QML-forrásai (Assets / preset kezelés)")
    roots = [root for label, root in _roots() if label == "install"]
    if not roots:
        log("  install mappa nem található")
        return
    root = os.path.join(roots[0], "resources")
    zpath = out_file("qml_sources.zip")
    total, nfiles, hits = 0, 0, []
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fns in os.walk(root):
            if "javascript-doc" in dp.lower():
                continue
            for f in fns:
                if not f.lower().endswith((".qml", ".js", ".qmltypes", "qmldir")):
                    continue
                fp = os.path.join(dp, f)
                size = os.path.getsize(fp)
                if total + size < 40 * 1024 * 1024:
                    z.write(fp, os.path.relpath(fp, root))
                    total += size
                    nfiles += 1
                try:
                    lines = open(fp, encoding="utf-8", errors="ignore").read().splitlines()
                except Exception:
                    continue
                topical = bool(QML_TOPIC.search(fp))
                for i, line in enumerate(lines):
                    if QML_HANDLER.search(line) and (topical or QML_TOPIC.search(line)):
                        ctx = " | ".join(x.strip() for x in lines[i:i + 3])
                        hits.append(f"{os.path.relpath(fp, root)}:{i + 1}: {ctx[:220]}")
    log(f"  zip: {zpath} ({nfiles} fájl, {total // 1024} KB)")
    log(f"  preset/tool/shelf jellegű kezelők ({len(hits)}, első 150):")
    for h in hits[:150]:
        log("   ", h)


def log_drop(mime, phase):
    """Az Assets ablakból behúzott elem mime-adatai (a Layout-szerkesztő behúzásos létrehozásához)."""
    section(f"6. Behúzás az Assets ablakból ({phase})")
    log(f"  formátumok: {list(mime.formats())}")
    log(f"  hasText={mime.hasText()} text={mime.text()[:500]!r}")
    log(f"  hasUrls={mime.hasUrls()} urls={[u.toString() for u in mime.urls()][:10]}")
    for f in mime.formats():
        data = bytes(mime.data(f))
        dec = ""
        for enc in ("utf-8", "utf-16-le"):
            try:
                dec = data.decode(enc)
                if dec.isprintable() or "resource://" in dec:
                    break
            except Exception:
                pass
        log(f"  [{f}] {len(data)} bájt: hex={data[:48].hex(' ')} szöveg={dec[:300]!r}")
    found = re.findall(r"resource://[^\s\"'\x00]+", mime.text() + " " + " ".join(
        bytes(mime.data(f)).decode("utf-8", "ignore") for f in mime.formats()))
    log(f"  talált resource URL-ek: {found[:10]}")
    return found


def run_discovery():
    for step in (api_presence, js_discovery, js_docs, ui_structure, qml_sources):
        guard(step)
    return flush()


# ----------------------------------------------------------------- A: show_in_ui
def try_show_in_ui(parent, r):
    section(f"2. A: show_in_ui() – {r.gui_name()}")
    guard(describe_resource, r)
    d = guard(assets_dock)
    if d is not None:
        log(f"  előtte: Assets visible={d.isVisible()} region_empty={d.visibleRegion().isEmpty()}")
    r.show_in_ui()
    wait(1500)
    if d is not None:
        log(f"  utána:  Assets visible={d.isVisible()} region_empty={d.visibleRegion().isEmpty()}")
    screenshot(d, "A_assets_after_show_in_ui.png")
    ask(parent, f"Látod az Assets ablakban kijelölve (kiemelve) ezt: „{r.gui_name()}”?")
    before = collect_texts(props_dock())
    wait_for_user(parent, f"Most kattints KÉZZEL egyszer a kijelölt „{r.gui_name()}” presetre az Assets ablakban.\n"
                          f"Ez az ablak nyitva maradhat. Ha rákattintottál, nyomd meg a gombot.",
                  "Rákattintottam")
    log_diff(before, collect_texts(props_dock()), "kézi kattintás után")
    wait_for_user(parent, PAINT_CHECK.format(name=r.gui_name()), "Festettem egy vonást")
    ask(parent, f"A kézi kattintás után a(z) „{r.gui_name()}” brush mintáját festette?")
    ask_text(parent, "Ha a Brush button csak KIJELÖLNÉ a presetet, és neked kellene még egyszer rákattintani,\n"
                     "mennyire lenne ez zavaró a munkában? Írd le pár szóban.")
    return flush()


# ----------------------------------------------------------------- B: JS
SETTER = re.compile(r"^(set|select|activate|apply|use|load|pick|choose)", re.I)
GETTER = re.compile(r"^(get|find|info|preview|thumbnail)", re.I)


def try_js(parent, r):
    section(f"3. B: JS API próbák – {r.gui_name()}")
    import substance_painter.js as js
    if not _JS_API:
        guard(js_discovery)
    url = r.identifier().url()
    funcs = [k for k, v in _JS_API.items() if v.startswith("function")]
    getters = [k for k in funcs if re.search(r"resource|shelf", k, re.I) and GETTER.search(k.rsplit(".", 1)[-1])]
    setters = [k for k in funcs if re.search(r"tool|brush|preset", k, re.I) and SETTER.search(k.rsplit(".", 1)[-1])
               and not re.search(r"mapexport|display|export", k, re.I)]
    log(f"  getter jelöltek ({len(getters)}): {getters}")
    log(f"  setter jelöltek ({len(setters)}): {setters}")
    getters = [g for g in getters if not g.endswith("findResources")]  # névvel kell hívni, nem URL-lel
    for g in getters[:20]:
        try:
            v = js.evaluate(f"JSON.stringify({g}({json.dumps(url)}))")
            log(f"  {g}(url) = {str(v)[:600]}")
        except Exception as e:
            log(f"  {g}(url) -> {type(e).__name__}: {str(e)[:200]}")
    if not setters:
        log("  NINCS tool/brush/preset beállító JS függvény a felderített névtérben.")
        return flush()
    for s in setters[:15]:
        before = collect_texts(props_dock())
        try:
            v = js.evaluate(f"JSON.stringify({s}({json.dumps(url)}))")
            log(f"  {s}(url) = {str(v)[:300]}")
        except Exception as e:
            log(f"  {s}(url) -> {type(e).__name__}: {str(e)[:300]}")
            continue
        wait(800)
        changed = log_diff(before, collect_texts(props_dock()), s)
        if changed:
            ask(parent, f"A(z) {s}() hívás után aktív lett a(z) „{r.gui_name()}” brush?")
    return flush()


# ----------------------------------------------------------------- C: Qt kattintás
def _qtest():
    try:
        from PySide6.QtTest import QTest
        return QTest
    except Exception:
        return None


def _send_click(target, local_pt, global_pt, double):
    QE, Qt = QtCore.QEvent, QtCore.Qt
    lp, gp = QtCore.QPointF(local_pt), QtCore.QPointF(global_pt)

    def ev(t):
        return QtGui.QMouseEvent(t, lp, gp, Qt.LeftButton,
                                 Qt.NoButton if t == QE.MouseButtonRelease else Qt.LeftButton, Qt.NoModifier)

    seq = [QE.MouseButtonPress, QE.MouseButtonRelease]
    if double:
        seq += [QE.MouseButtonPress, QE.MouseButtonDblClick, QE.MouseButtonRelease]
    for t in seq:
        QtCore.QCoreApplication.sendEvent(target, ev(t))
        QtWidgets.QApplication.processEvents()


def _find_candidates(r):
    """Az Assets ablakban a preset nevét viselő elemek: (leírás, kattintó függvény(double), kép-forrás item)."""
    name = r.gui_name()
    d = assets_dock()
    cands = []
    if d is None:
        log("  Assets dock nem található")
        return cands
    # widget alapú nézetek
    for view in live_children(d, QtWidgets.QAbstractItemView):
        m = view.model()
        if m is None:
            continue
        hits = m.match(m.index(0, 0), QtCore.Qt.DisplayRole, name, 1,
                       QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive)
        for idx in hits:
            view.scrollTo(idx)
            rect = view.visualRect(idx)

            def click(double, view=view, rect=rect, idx=idx):
                vp = view.viewport()
                c = rect.center()
                qt = _qtest()
                if qt is not None:
                    (qt.mouseDClick if double else qt.mouseClick)(vp, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, c)
                    return "QTest"
                _send_click(vp, c, vp.mapToGlobal(c), double)
                return "sendEvent"

            cands.append((f"QAbstractItemView {view.metaObject().className()} rect={rect}", click, None,
                          QtCore.QRect(view.viewport().mapToGlobal(rect.topLeft()), rect.size())))
    # QML alapú nézetek
    for sname, root, target, to_global in quick_surfaces(global_rect(d)):
        for depth, item, cls, props in qml_items(root):
            if not any(v == name for v in props.values()):
                continue
            # a delegate: néhány szinttel feljebb, ahol már kép is van
            deleg, img = item, None
            for _ in range(4):
                p = deleg.parentItem()
                if p is None:
                    break
                deleg = p
                imgs = [(c2, pr) for _, c2, cl, pr in qml_items(deleg, limit=200) if "Image" in cl and "source" in pr]
                if imgs:
                    img = imgs[0]
                    break
            center = deleg.mapToScene(QtCore.QPointF(deleg.width() / 2, deleg.height() / 2))
            tl = to_global(deleg.mapToScene(QtCore.QPointF(0, 0)))
            grect = QtCore.QRect(tl, QtCore.QSize(int(deleg.width()), int(deleg.height())))

            def click(double, target=target, center=center, to_global=to_global):
                qt = _qtest()
                if qt is not None and isinstance(target, QtGui.QWindow):
                    try:
                        (qt.mouseDClick if double else qt.mouseClick)(target, QtCore.Qt.LeftButton,
                                                                       QtCore.Qt.NoModifier, center.toPoint())
                        return "QTest(QWindow)"
                    except Exception as e:
                        log("    QTest QWindow hiba, sendEvent-re váltok:", e)
                _send_click(target, center, QtCore.QPointF(to_global(center)), double)
                return "sendEvent"

            cands.append((f"QML {cls} {props} delegate={deleg.metaObject().className()} "
                          f"{int(deleg.width())}x{int(deleg.height())} kép={img[1] if img else None} @ {sname}",
                          click, img[0] if img else None, grect))
    return cands


def try_qt_click(parent, r):
    section(f"4. C: Qt/QML kattintás szimulálása – {r.gui_name()}")
    r.show_in_ui()
    wait(1500)
    cands = _find_candidates(r)
    log(f"  {len(cands)} jelölt elem a(z) „{r.gui_name()}” névvel:")
    for desc, *_ in cands:
        log("   ", desc)
    if not cands:
        screenshot(assets_dock(), "C_assets_no_candidate.png")
        return flush()
    desc, click, _, grect = cands[0]
    log(f"  célpont: {desc} global_rect={grect}")
    crop_screen(grect.adjusted(-20, -20, 20, 20), "C_target.png")
    methods = (("Qt esemény, egy kattintás", lambda: click(False)),
               ("Qt esemény, dupla kattintás", lambda: click(True)),
               ("Windows egér, egy kattintás", lambda: os_click(grect.center(), False)),
               ("Windows egér, dupla kattintás", lambda: os_click(grect.center(), True)))
    for n, (label, fn) in enumerate(methods):
        r.show_in_ui()
        wait(1000)
        before = collect_texts(props_dock())
        screenshot(props_dock(), f"C_{n}_props_before.png")
        how = guard(fn)
        wait(1000)
        screenshot(props_dock(), f"C_{n}_props_after.png")
        log(f"  [{n}] {label} ({how})")
        log_diff(before, collect_texts(props_dock()), label)
        wait_for_user(parent, f"Szimulált kattintás történt: {label}.\n\n" + PAINT_CHECK.format(name=r.gui_name()),
                      "Festettem egy vonást")
        if ask(parent, f"[{label}] Most a(z) „{r.gui_name()}” brush mintáját festette?") == "IGEN":
            break
    return flush()


def crop_screen(grect, name):
    try:
        scr = QtGui.QGuiApplication.screenAt(grect.center()) or QtGui.QGuiApplication.primaryScreen()
        geo = scr.geometry()
        pix = scr.grabWindow(0, grect.x() - geo.x(), grect.y() - geo.y(), grect.width(), grect.height())
        path = out_file(name)
        pix.save(path)
        log(f"  kivágás: {path} ({pix.width()}x{pix.height()})")
    except Exception as e:
        log(f"  kivágás hiba ({name}): {e}")


def os_click(gp, double):
    """Valódi Windows egérkattintás (SetCursorPos + mouse_event), utána az egér visszakerül."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    scr = QtGui.QGuiApplication.screenAt(gp) or QtGui.QGuiApplication.primaryScreen()
    g, dpr = scr.geometry(), scr.devicePixelRatio()
    x = int(round(g.x() + (gp.x() - g.x()) * dpr))
    y = int(round(g.y() + (gp.y() - g.y()) * dpr))
    old = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(old))
    u.SetCursorPos(x, y)
    wait(80)
    for _ in range(2 if double else 1):
        u.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
        u.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
        wait(60)
    wait(300)
    u.SetCursorPos(old.x, old.y)
    return f"Windows egér: logikai {gp.x()},{gp.y()} -> fizikai {x},{y} (dpr={dpr}, képernyő={scr.name()})"


# ----------------------------------------------------------------- ikon
def _extract_embedded_image(path):
    data = open(path, "rb").read()
    log(f"    {path}: {len(data)} bájt, eleje={data[:32].hex(' ')}, zip={zipfile.is_zipfile(path)}")
    strs = re.findall(rb"[ -~]{6,}", data[:200000])
    log(f"    olvasható szövegek ({len(strs)}, első 40): {[x[:60].decode() for x in strs[:40]]}")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            log(f"    zip tartalom: {names[:30]}")
            for n in names:
                if n.lower().endswith((".png", ".jpg", ".jpeg")):
                    dst = out_file("T2_zip_" + os.path.basename(n))
                    open(dst, "wb").write(z.read(n))
                    log(f"    KÉP KIMENTVE: {dst}")
                    return
    for sig, end, ext in ((b"\x89PNG\r\n\x1a\n", b"IEND\xaeB`\x82", ".png"), (b"\xff\xd8\xff", b"\xff\xd9", ".jpg")):
        i = data.find(sig)
        if i >= 0:
            j = data.find(end, i)
            if j > i:
                dst = out_file("T2_embedded" + ext)
                open(dst, "wb").write(data[i:j + len(end)])
                log(f"    BEÁGYAZOTT KÉP KIMENTVE: {dst}")
                return
    log("    nincs benne felismerhető kép")


def scan_thumbnail_cache():
    """A LOCALAPPDATA / APPDATA Painter-mappák kiterjesztés nélküli fájljai: van-e köztük kép (thumbnail-cache)?"""
    log("  T2b: lehetséges thumbnail-cache a LOCALAPPDATA / APPDATA alatt")
    sigs = ((b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpg"), (b"RIFF", "riff/webp"), (b"DDS ", "dds"),
            (b"PK\x03\x04", "zip"), (b"SQLite format", "sqlite"))
    for env in ("LOCALAPPDATA", "APPDATA"):
        root = os.path.join(os.environ.get(env, ""), "Adobe", "Adobe Substance 3D Painter")
        if not os.path.isdir(root):
            continue
        dirs, kinds, saved = {}, {}, 0
        for dp, _, fns in os.walk(root):
            rel = os.path.relpath(dp, root)
            dirs[rel] = len(fns)
            for f in fns:
                fp = os.path.join(dp, f)
                try:
                    head = open(fp, "rb").read(16)
                except Exception:
                    continue
                kind = next((k for sig, k in sigs if head.startswith(sig)), "egyéb")
                kinds[kind] = kinds.get(kind, 0) + 1
                if kind in ("png", "jpg") and saved < 12:
                    dst = out_file(f"T2b_{env}_{saved}.{kind}")
                    with open(fp, "rb") as a, open(dst, "wb") as b:
                        b.write(a.read())
                    log(f"    kép: {fp} ({os.path.getsize(fp)} bájt) -> {dst}")
                    saved += 1
        log(f"    [{env}] mappák (fájlszám): {sorted(dirs.items(), key=lambda kv: -kv[1])[:20]}")
        log(f"    [{env}] fájltípusok a fejléc alapján: {kinds}")


def try_icons(parent, r):
    section(f"5. Ikon próbák – {r.gui_name()}")
    rid = r.identifier()
    # T2: fájl a lemezen – elsőként a JS API által megadott pontos útvonal
    paths = []
    try:
        import substance_painter.js as js
        info = json.loads(js.evaluate(f"JSON.stringify(alg.resources.getResourceInfo({json.dumps(rid.url())}))"))
        log(f"  getResourceInfo: {info}")
        if info.get("filePath"):
            paths.append(info["filePath"])
    except Exception as e:
        log(f"  getResourceInfo hiba: {e}")
    index, _ = build_file_index()
    keys = {rid.name.lower(), r.gui_name().lower(), os.path.basename(rid.name).lower()}
    paths += sorted({p for k in keys for p in index.get(k, [])} - set(os.path.normpath(x) for x in paths))
    log(f"  T2: {len(paths)} azonos nevű fájl: {paths[:20]}")
    for p in paths[:6]:
        guard(_extract_embedded_image, p)
    guard(scan_thumbnail_cache)
    # T3: képernyőkép és QML Image
    r.show_in_ui()
    wait(1500)
    cands = _find_candidates(r)
    for i, (desc, _, img, grect) in enumerate(cands[:3]):
        log(f"  T3 jelölt {i}: {desc}")
        scr = QtGui.QGuiApplication.screenAt(grect.center()) or QtGui.QGuiApplication.primaryScreen()
        geo = scr.geometry()
        pix = scr.grabWindow(0, grect.x() - geo.x(), grect.y() - geo.y(), grect.width(), grect.height())
        p = out_file(f"T3_crop_{i}.png")
        pix.save(p)
        log(f"    képernyő-kivágás: {p} ({pix.width()}x{pix.height()})")
        if img is not None:
            src = str(img.property("source").toString() if hasattr(img.property("source"), "toString") else img.property("source"))
            log(f"    QML Image source = {src}")
            if src.startswith("file:"):
                local = QtCore.QUrl(src).toLocalFile()
                log(f"    FÁJL-ALAPÚ THUMBNAIL: {local} létezik={os.path.exists(local)}")
            try:
                gr = img.grabToImage()
                done = []
                gr.ready.connect(lambda: done.append(gr.saveToFile(out_file(f"T3_qml_image_{i}.png"))))
                for _ in range(100):
                    if done:
                        break
                    wait(30)
                log(f"    grabToImage: {'mentve' if done and done[0] else 'nem sikerült'} -> {out_file(f'T3_qml_image_{i}.png')}")
            except Exception as e:
                log(f"    grabToImage hiba: {e}")
    if not cands:
        log("  T3: nincs jelölt elem az Assets ablakban")
    QtWidgets.QMessageBox.information(parent, "SPX Brush Probe",
                                      f"Nyisd meg a riport mappát, és nézd meg a T2_* / T3_* képeket.\n"
                                      f"Utána válaszolj a kérdésre.")
    ask(parent, f"Van a T2_* / T3_* képek között olyan, amelyik a(z) „{r.gui_name()}” brush thumbnailje, "
                f"és Button ikonnak jó lenne?")
    return flush()


# ----------------------------------------------------------------- v3.5: ikon a modellből, previews
_ROLES = list(range(0, 16)) + list(range(256, 300))


def _safe(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name)[:40]


def _model_hits(name):
    """(nézet, index) párok az Assets ablak widget-nézeteiben, ahol a DisplayRole == name."""
    d = assets_dock()
    if d is None:
        return []
    out = []
    for view in live_children(d, QtWidgets.QAbstractItemView):
        m = view.model()
        if m is None:
            continue
        for idx in m.match(m.index(0, 0), QtCore.Qt.DisplayRole, name, 1,
                           QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive):
            out.append((view, idx))
    return out


def _save_visual(v, base):
    if isinstance(v, QtGui.QIcon):
        sizes = [(s.width(), s.height()) for s in v.availableSizes()]
        pm = v.pixmap(QtCore.QSize(512, 512))
        if pm.isNull():
            return f"QIcon availableSizes={sizes} üres pixmap", None
        path = base + ".png"
        pm.save(path)
        return f"QIcon availableSizes={sizes} pixmap(512) -> {pm.width()}x{pm.height()} -> {path}", path
    if isinstance(v, (QtGui.QPixmap, QtGui.QImage)):
        if v.isNull():
            return f"{type(v).__name__} üres", None
        path = base + ".png"
        v.save(path)
        return f"{type(v).__name__} {v.width()}x{v.height()} -> {path}", path
    return None, None


def _save_tooltip_image(html, base):
    """A tooltip HTML-be ágyazott data:image/...;base64 kép kimentése. 12.2-n 256x256 PNG."""
    import base64
    m = re.search(r"data:image/(\w+);base64,([A-Za-z0-9+/=]+)", html)
    if not m:
        return None, None
    data = base64.b64decode(m.group(2))
    img = QtGui.QImage.fromData(data)
    path = base + "." + m.group(1)
    open(path, "wb").write(data)
    rest = re.sub(r"<img[^>]*>", "<img…>", html)
    return (f"tooltip-kép {m.group(1)} {len(data)} bájt {img.width()}x{img.height()} -> {path}; "
            f"tooltip többi része: {rest[:300]!r}"), path


def icon_from_model(r, tag):
    """T4: a csempe ikonja közvetlenül a modellből. Visszaad: a mentett képek útvonalai."""
    name = r.gui_name()
    hits = _model_hits(name)
    if not hits:
        r.show_in_ui()
        wait(1500)
        hits = _model_hits(name)
    log(f"  T4 [{tag}] „{name}”: {len(hits)} találat a modellben")
    saved = []
    if not hits:
        return saved
    view, idx = hits[0]
    m = view.model()
    try:
        rn = {int(k): bytes(v).decode(errors="replace") for k, v in m.roleNames().items()}
    except Exception as e:
        rn = {}
        log(f"    roleNames hiba: {e}")
    log(f"    nézet={view.metaObject().className()} modell={m.metaObject().className()} "
        f"iconSize={view.iconSize().width()}x{view.iconSize().height()} roleNames={rn}")
    for role in sorted(set(_ROLES) | set(rn)):
        try:
            v = idx.data(role)
        except Exception as e:
            log(f"    role {role}: hiba {e}")
            continue
        if v is None:
            continue
        desc, path = _save_visual(v, out_file(f"T4_{tag}_{_safe(name)}_role{role}"))
        if desc is None and isinstance(v, str) and "data:image/" in v:
            desc, path = _save_tooltip_image(v, out_file(f"T4t_{tag}_{_safe(name)}_tooltip"))
            if path:
                saved.insert(0, path)  # a legnagyobb felbontású: ezt mutatja a behúzás
        if desc is None:
            text = repr(v)
            desc = f"{type(v).__name__} {text[:160]}"
        elif path:
            saved.append(path)
        log(f"    role {role} ({rn.get(role, '')}): {desc}")
    # a thumbnail lehet, hogy késleltetve töltődik be
    wait(1500)
    desc, path = _save_visual(idx.data(QtCore.Qt.DecorationRole), out_file(f"T4_{tag}_{_safe(name)}_late"))
    log(f"    DecorationRole 1,5 s múlva: {desc}")
    if path:
        saved.append(path)
    # T4c: a csempe kirajzolva a widgetből (nem a képernyőről, így takarás nem zavarja)
    try:
        view.scrollTo(idx)
        rect = view.visualRect(idx)
        pm = view.viewport().grab(rect)
        path = out_file(f"T4c_{tag}_{_safe(name)}_grab.png")
        pm.save(path)
        log(f"    T4c widget-grab: {rect.width()}x{rect.height()} dpr={pm.devicePixelRatio()} -> {path}")
    except Exception as e:
        log(f"    T4c hiba: {e}")
    return saved


def embedded_png_present(r):
    """Gyors T2: van-e beágyazott PNG a preset fájljában (szövegdump nélkül)."""
    try:
        import substance_painter.js as js
        info = json.loads(js.evaluate(
            f"JSON.stringify(alg.resources.getResourceInfo({json.dumps(r.identifier().url())}))"))
        fp = info.get("filePath") or ""
    except Exception as e:
        return f"getResourceInfo hiba: {e}"
    if not fp or not os.path.isfile(fp):
        return f"nincs fájl ({fp!r})"
    data = open(fp, "rb").read()
    i = data.find(b"\x89PNG\r\n\x1a\n")
    kind = os.path.splitext(fp)[1]
    return f"{kind} {len(data)} bájt, beágyazott PNG: {'VAN' if i >= 0 else 'NINCS'} ({fp})"


def scan_previews(rs):
    """T5: a %APPDATA%\\Adobe\\Adobe Substance 3D Painter\\previews formátuma, és van-e név szerinti egyezés."""
    root = os.path.join(os.environ.get("APPDATA", ""), "Adobe", "Adobe Substance 3D Painter", "previews")
    log(f"  T5 previews: {root} létezik={os.path.isdir(root)}")
    if not os.path.isdir(root):
        return
    files = []
    for dp, _, fns in os.walk(root):
        for f in fns:
            files.append(os.path.join(dp, f))
    sizes = sorted(os.path.getsize(f) for f in files) or [0]
    log(f"    {len(files)} fájl, méret min/medián/max: {sizes[0]}/{sizes[len(sizes) // 2]}/{sizes[-1]}")
    log(f"    minta nevek: {[os.path.relpath(f, root) for f in files[:15]]}")
    keys = set()
    for r in rs:
        rid = r.identifier()
        keys |= {rid.name.lower(), r.gui_name().lower(), (rid.version or "").split(".")[0].lower()}
    keys.discard("")
    matches = [f for f in files if any(k in os.path.relpath(f, root).lower() for k in keys)]
    log(f"    név/verzió szerinti egyezés ({len(keys)} kulcs): {[os.path.relpath(f, root) for f in matches[:10]]}")
    newest = sorted(files, key=os.path.getmtime, reverse=True)[:3]
    for n, f in enumerate(matches[:3] + [x for x in newest if x not in matches]):
        head = open(f, "rb").read(32)
        rd = QtGui.QImageReader(f)
        fmt = bytes(rd.format()).decode() or "-"
        img = rd.read()
        log(f"    {os.path.relpath(f, root)}: {os.path.getsize(f)} bájt, eleje={head.hex(' ')}, "
            f"Qt formátum={fmt}, kép={'nem' if img.isNull() else f'{img.width()}x{img.height()}'}")
        if not img.isNull():
            img.save(out_file(f"T5_{n}.png"))
        elif os.path.getsize(f) < 2_000_000:
            with open(f, "rb") as a, open(out_file(f"T5_{n}_raw.bin"), "wb") as b:
                b.write(a.read())


def _pick_batch(presets, current):
    """A kiválasztott + néhány tipikus eset: beépített beágyazott PNG nélkül / vele, BRUSH (alpha), saját preset."""
    picks, seen = [], set()

    def add(tag, r):
        if r is None:
            return
        u = r.identifier().url()
        if u not in seen:
            seen.add(u)
            picks.append((tag, r))

    add("kivalasztott", current)
    by_name = {r.gui_name(): r for _, r in presets}
    for n in ("Basic Hard", "Ivy Branch", "Cracks"):
        add(_safe(n), by_name.get(n))
    add("brush_alpha", next((r for label, r in presets if "[BRUSH]" in label
                             and not r.identifier().url().endswith(".sppr")), None))
    add("sajat", next((r for _, r in presets if r.identifier().context == "your_assets"), None))
    return picks


def icon_batch(parent, presets, current):
    section("7. Ikon sorozat (v3.5): T2 beágyazott PNG, T4 modell, T4c widget-grab, T5 previews")
    picks = _pick_batch(presets, current)
    log(f"  próbált presetek: {[(t, r.gui_name(), r.identifier().url()) for t, r in picks]}")
    for tag, r in picks:
        log(f"  --- {tag}: {r.gui_name()}")
        log(f"    T2: {guard(embedded_png_present, r)}")
        guard(icon_from_model, r, tag)
    flush()
    QtWidgets.QMessageBox.information(parent, "SPX Brush Probe",
                                      "Nyisd meg a riport mappát, és nézd meg a T4t_… (tooltip) képeket.\n"
                                      "Utána válaszolj a kérdésekre.")
    ask(parent, "A T4t_… képek (a „tooltip” végűek) mind a saját brushuk nagy, éles képei?")
    ask(parent, "Ugyanaz a kép, mint amit a Painter mutat, ha az Assets ablakban a brush fölé viszed az egeret?")
    ask_text(parent, "Ha valami furcsa volt a képeken (rossz brush, üres, homályos, felirat), írd le pár szóban.")
    return flush()


def icon_for_drop(url, presets):
    """Behúzáskor: a behúzott resource ikonja a modellből. Visszaad: (Resource vagy None, kép útvonal vagy None)."""
    base = url.split("?")[0]
    r = next((r for label, r in presets if base in label), None)
    if r is None:
        try:
            r = (res.Resource.retrieve(res.ResourceID.from_url(url)) or [None])[0]
        except Exception as e:
            log(f"  retrieve({url}) hiba: {e}")
    if r is None:
        log(f"  behúzott resource nem található: {url}")
        return None, None
    section(f"6b. Behúzott brush ikonja – {r.gui_name()}")
    log(f"    T2: {guard(embedded_png_present, r)}")
    paths = guard(icon_from_model, r, "drop") or []
    return r, (paths[0] if paths else None)
