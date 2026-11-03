# PROTOTYPE – eldobható kód, nem kerül a main ágra.
# A „Prototype: Brush button aktiválás és ikon a hivatalos API hiányában” ticket próbái.
# Riportok: %APPDATA%\spx_brush_probe\
#
# Jelöltek:
#   A  Resource.show_in_ui()               – hivatalos, csak kijelöl
#   B  substance_painter.js.evaluate()     – legacy JS API felderítése és a talált függvények kipróbálása
#   C  Qt/QML UI-automatizálás             – kattintás szimulálása az Assets ablak elemén
#   T2 thumbnail a preset fájlból / cache-ből
#   T3 thumbnail képernyőképből / QML Image elemből

import io, os, re, sys, json, time, zipfile, traceback

from PySide6 import QtCore, QtGui, QtWidgets

import substance_painter.resource as res
import substance_painter.ui as ui

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


def main_window():
    return ui.get_main_window()


def alive(o):
    """False, ha a Python wrapper mögötti C++ objektum már törölve van (11.1 „ghost widget”)."""
    try:
        import shiboken6
        if not shiboken6.isValid(o):
            return False
        o.objectName()
        return True
    except Exception:
        return False


def live_children(parent, cls):
    return [c for c in parent.findChildren(cls) if alive(c)]


_DEAD_REPORTED = set()


def find_dock(object_name, title_part):
    all_docks = main_window().findChildren(QtWidgets.QDockWidget)
    docks = [d for d in all_docks if alive(d)]
    dead = len(all_docks) - len(docks)
    if dead and dead not in _DEAD_REPORTED:
        _DEAD_REPORTED.add(dead)
        log(f"  FIGYELEM: {dead} törölt (halott) QDockWidget wrapper a findChildren eredményében")
    for d in docks:
        if d.objectName() == object_name:
            return d
    for d in docks:
        if title_part.lower() in d.windowTitle().lower():
            return d
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
    section("0. Presetek listázása")
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


def dump_widget_tree(w, depth=0, maxd=12, lines=None):
    lines = [] if lines is None else lines
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
        extra += f" MODEL rows={m.rowCount()} cols={m.columnCount()} minta={sample}"
    lines.append("  " * depth + f"{w.metaObject().className()} '{w.objectName()}' "
                 f"vis={w.isVisible()} {w.width()}x{w.height()}{extra}")
    for c in w.children():
        if isinstance(c, QtWidgets.QWidget) and alive(c):
            dump_widget_tree(c, depth + 1, maxd, lines)
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


def run_discovery():
    for step in (api_presence, js_discovery, js_docs, ui_structure):
        guard(step)
    return flush()


# ----------------------------------------------------------------- A: show_in_ui
def try_show_in_ui(parent, r):
    section(f"2. A: show_in_ui() – {r.gui_name()}")
    guard(describe_resource, r)
    d = assets_dock()
    if d is not None:
        log(f"  előtte: Assets visible={d.isVisible()} region_empty={d.visibleRegion().isEmpty()}")
    r.show_in_ui()
    wait(1500)
    if d is not None:
        log(f"  utána:  Assets visible={d.isVisible()} region_empty={d.visibleRegion().isEmpty()}")
    screenshot(d, "A_assets_after_show_in_ui.png")
    ask(parent, f"Látod az Assets ablakban kijelölve (kiemelve) ezt: „{r.gui_name()}”?")
    before = collect_texts(props_dock())
    QtWidgets.QMessageBox.information(parent, "SPX Brush Probe",
                                      "Most kattints KÉZZEL a kijelölt presetre az Assets ablakban,\n"
                                      "majd gyere vissza, és nyomd meg az OK-t.")
    log_diff(before, collect_texts(props_dock()), "kézi kattintás után")
    ask(parent, f"A kézi kattintás után aktív lett a(z) „{r.gui_name()}” brush (a Properties – Paint panelen látszik)?")
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
    desc, click, _, _ = cands[0]
    for double in (False, True):
        before = collect_texts(props_dock())
        screenshot(props_dock(), f"C_props_before_{'dbl' if double else 'single'}.png")
        how = guard(click, double)
        wait(1000)
        screenshot(props_dock(), f"C_props_after_{'dbl' if double else 'single'}.png")
        label = "dupla kattintás" if double else "egy kattintás"
        log(f"  {label} ({how})")
        log_diff(before, collect_texts(props_dock()), label)
        if ask(parent, f"Szimulált {label.upper()} történt a(z) „{r.gui_name()}” presetre.\n"
                       f"Aktív lett ez a brush (a Properties – Paint panelen látszik)?") == "IGEN":
            break
    return flush()


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
