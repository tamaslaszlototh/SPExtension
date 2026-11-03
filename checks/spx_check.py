# SPExtension gépdiagnosztika (Task: telepítési és hálózati ellenőrzések a két gépen)
#
# Használat: Painter -> Python menü -> (Python konzol / Script editor), a teljes fájl
# tartalmát bemásolni és lefuttatni. A riport ide kerül:
#     %TEMP%\spx_check_<painter verzió>.txt
# Ezt a fájlt kell visszaküldeni / a tickethez kommentbe tenni.
#
# A Layer stack (ScopedModification) próbákhoz legyen nyitva egy ELDOBHATÓ projekt
# (pl. File > New egy tetszőleges meshsel). A szkript létrehoz és töröl fill layereket.
# Ha nincs nyitott projekt, ez a rész kimarad.

import io, os, sys, json, ssl, time, platform, traceback, tempfile

OUT = io.StringIO()


def log(*a):
    print(*a, file=OUT)


def section(title):
    log("")
    log("=" * 70)
    log(title)
    log("=" * 70)


def guard(fn):
    try:
        fn()
    except Exception:
        log("!! KIVÉTEL:")
        log(traceback.format_exc())


# --------------------------------------------------------------------------
def versions():
    section("1. Verziók")
    import substance_painter as sp
    try:
        import substance_painter.application as app
        log("Painter version_info:", app.version_info())
        log("Painter version:", app.version())
    except Exception as e:
        log("Painter verzió nem olvasható:", e)
    log("Python API version:", getattr(sp, "__version__", "?"))
    log("Python:", sys.version)
    log("Platform:", platform.platform())
    import PySide6
    from PySide6 import QtCore
    log("PySide6.__version__:", PySide6.__version__)
    log("qVersion():", QtCore.qVersion())
    log("OpenSSL (Python):", ssl.OPENSSL_VERSION)


def paths():
    section("2. Útvonalak, Documents / OneDrive")
    import substance_painter_plugins as spp
    log("substance_painter_plugins.path:", spp.path)
    for root in spp.path:
        p = os.path.join(root, "plugins")
        log("  plugins mappa:", p, "létezik" if os.path.isdir(p) else "NINCS")
    for k in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "OneDrive", "OneDriveCommercial",
              "SUBSTANCE_PAINTER_PLUGINS_PATH", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        log(f"  env {k} =", os.environ.get(k) or os.environ.get(k.lower()))
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        log("  Registry 'Personal' (Documents):", winreg.QueryValueEx(key, "Personal")[0])
    except Exception as e:
        log("  Registry Documents nem olvasható:", e)
    # Írhatóság
    for base in (os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        d = os.path.join(base, "SPExtension_probe")
        try:
            os.makedirs(d, exist_ok=True)
            f = os.path.join(d, "w.txt")
            with open(f, "w") as fh:
                fh.write("ok")
            os.replace(f, f + ".renamed")
            os.remove(f + ".renamed")
            os.rmdir(d)
            log("  írható + os.replace OK:", base)
        except Exception as e:
            log("  NEM írható:", base, e)
    for root in spp.path:
        d = os.path.join(root, "plugins")
        if os.path.isdir(d):
            try:
                t = os.path.join(d, "_spx_write_test.tmp")
                open(t, "w").close()
                os.remove(t)
                log("  plugins mappa írható:", d)
            except Exception as e:
                log("  plugins mappa NEM írható:", d, e)


def proxy_info():
    section("3. Proxy beállítások")
    import urllib.request
    log("urllib.getproxies():", urllib.request.getproxies())
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        for name in ("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL", "AutoDetect"):
            try:
                log(f"  {name} =", winreg.QueryValueEx(key, name)[0])
            except FileNotFoundError:
                log(f"  {name} = (nincs)")
    except Exception as e:
        log("  Internet Settings nem olvasható:", e)


UA = {"User-Agent": "SPExtension-check/0.1", "Accept": "application/vnd.github+json"}
# A SPExtension repo még privát, ezért egy publikus repóval teszteljük ugyanazt az utat.
API_URL = "https://api.github.com/repos/cli/cli/releases/latest"


def _urlopen(url, ctx, headers=UA, read=4096):
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    t = time.time()
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        data = r.read(read)
        return r.status, r.geturl(), data, time.time() - t


def network_urllib():
    section("4. Hálózat: urllib (api.github.com + asset redirect)")
    ctx = ssl.create_default_context()
    log("verify_flags:", ctx.verify_flags)
    asset_url = None
    for label, c in (("default context", ctx), ("X509_STRICT nélkül", None)):
        if c is None:
            c = ssl.create_default_context()
            c.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
        try:
            status, final, data, dt = _urlopen(API_URL, c, read=10_000_000)
            j = json.loads(data)
            log(f"  [{label}] API OK: {status} {dt:.2f}s tag={j.get('tag_name')}")
            assets = [a for a in j.get("assets", []) if a["name"].endswith(".zip")]
            if assets:
                asset_url = assets[0]["browser_download_url"]
            break
        except Exception as e:
            log(f"  [{label}] API HIBA: {type(e).__name__}: {e}")
    if asset_url:
        try:
            status, final, data, dt = _urlopen(asset_url, ctx, headers={"User-Agent": UA["User-Agent"]})
            log(f"  zip asset OK: {status} {dt:.2f}s, végső host: {final.split('/')[2]}, első bájtok: {data[:2]!r}")
        except Exception as e:
            log(f"  zip asset HIBA: {type(e).__name__}: {e}")


def network_qt():
    section("5. Hálózat: PySide6.QtNetwork rendszer-proxyval")
    try:
        from PySide6 import QtNetwork, QtCore
    except Exception as e:
        log("  QtNetwork NEM elérhető:", e)
        return
    log("  QSslSocket.supportsSsl():", QtNetwork.QSslSocket.supportsSsl())
    try:
        log("  TLS backendek:", QtNetwork.QSslSocket.availableBackends(),
            "aktív:", QtNetwork.QSslSocket.activeBackend())
    except Exception:
        pass
    QtNetwork.QNetworkProxyFactory.setUseSystemConfiguration(True)
    q = QtNetwork.QNetworkProxyQuery(QtCore.QUrl(API_URL))
    log("  rendszer-proxy erre a URL-re:",
        [(p.type(), p.hostName(), p.port()) for p in QtNetwork.QNetworkProxyFactory.systemProxyForQuery(q)])
    nam = QtNetwork.QNetworkAccessManager()
    req = QtNetwork.QNetworkRequest(QtCore.QUrl(API_URL))
    req.setRawHeader(b"User-Agent", UA["User-Agent"].encode())
    req.setAttribute(QtNetwork.QNetworkRequest.RedirectPolicyAttribute,
                     QtNetwork.QNetworkRequest.NoLessSafeRedirectPolicy)
    loop = QtCore.QEventLoop()
    reply = nam.get(req)
    reply.finished.connect(loop.quit)
    QtCore.QTimer.singleShot(10000, loop.quit)
    loop.exec()
    if not reply.isFinished():
        reply.abort()
        log("  Qt kérés: TIMEOUT (10s)")
        return
    code = reply.attribute(QtNetwork.QNetworkRequest.HttpStatusCodeAttribute)
    log("  Qt kérés:", code, "hiba:", reply.error(), reply.errorString())


def plugin_state():
    section("6. Plugin állapot")
    import substance_painter_plugins as spp
    log("  betöltött pluginok:", [m.__name__ for m in spp.plugins.keys()] if hasattr(spp, "plugins") else "?")
    log("  spx_probe betöltve:", "spx_probe" in sys.modules)
    probe_log = os.path.join(os.environ.get("APPDATA", ""), "spx_probe.log")
    if os.path.exists(probe_log):
        log("  spx_probe.log tartalma:")
        log(open(probe_log, encoding="utf-8").read())


def layerstack():
    section("7. Layer stack / ScopedModification")
    import substance_painter.project as project
    if not project.is_open():
        log("  Nincs nyitott projekt, kihagyva.")
        return
    import substance_painter.layerstack as ls
    import substance_painter.textureset as ts
    stack = ts.get_active_stack()

    def roots():
        return [n.uid() for n in ls.get_root_layer_nodes(stack)]

    def top():
        return ls.InsertPosition.from_textureset_stack(stack)

    # 7a: kivétel a scope-ban
    before = roots()
    try:
        with ls.ScopedModification("SPX probe: kivétel"):
            ls.insert_fill(top())
            raise RuntimeError("szándékos")
    except RuntimeError:
        pass
    after = roots()
    log(f"  7a kivétel a scope-ban: rétegek {len(before)} -> {len(after)} "
        f"({'MEGMARADT a félkész változás' if len(after) > len(before) else 'visszagörgetve'})")
    for uid in set(after) - set(before):
        ls.delete_node(ls.get_node_by_uid(uid))

    # 7b: egymásba ágyazás
    before = roots()
    try:
        with ls.ScopedModification("SPX probe: külső"):
            ls.insert_fill(top())
            with ls.ScopedModification("SPX probe: belső"):
                ls.insert_fill(top())
        log(f"  7b egymásba ágyazás: nincs kivétel, rétegek {len(before)} -> {len(roots())}")
    except Exception as e:
        log(f"  7b egymásba ágyazás: KIVÉTEL {type(e).__name__}: {e}")

    # 7c: kijelölés-módosítás scope-on belül és kívül
    nodes = ls.get_root_layer_nodes(stack)
    try:
        with ls.ScopedModification("SPX probe: kijelölés"):
            ls.set_selected_nodes([nodes[-1]])
        log("  7c kijelölés scope-ban: nincs kivétel")
    except Exception as e:
        log(f"  7c kijelölés scope-ban: KIVÉTEL {type(e).__name__}: {e}")
    ls.set_selected_nodes([nodes[0]])
    log("  7c -> KÉZI: nézd meg a History panelt: látszik-e 'selection' jellegű bejegyzés,")
    log("     és hány bejegyzés lett a 'SPX probe: külső' / 'belső' próbából (1 vagy 2?).")
    log("     Ezután Ctrl+Z-vel visszavonhatod a próbarétegeket.")


def menu_actions():
    section("8. QAction-ök, menük, QML, resource-ok")
    from PySide6 import QtGui, QtWidgets, QtCore
    import substance_painter.ui as ui
    mw = ui.get_main_window()
    rows = []
    for a in mw.findChildren(QtGui.QAction):
        owners = [o.objectName() or type(o).__name__ for o in a.associatedObjects()]
        rows.append((a.objectName(), a.text().replace("&", ""), a.shortcut().toString(),
                     not a.icon().isNull(), [(s.width(), s.height()) for s in a.icon().availableSizes()],
                     a.isEnabled(), owners))
    log(len(rows), "QAction,", sum(1 for r in rows if r[3]), "ikonnal")
    for r in sorted(rows, key=lambda r: r[1]):
        log(" ", r)
    log("Menük:", [(m.objectName(), m.title()) for m in mw.menuBar().findChildren(QtWidgets.QMenu)])
    try:
        from PySide6 import QtQuickWidgets
        log("QQuickWidgets:", [(w.objectName(), w.source().toString())
                               for w in mw.findChildren(QtQuickWidgets.QQuickWidget)])
    except Exception as e:
        log("QtQuickWidgets nem elérhető:", e)
    log("Dock widgetek:", [(d.objectName(), d.windowTitle()) for d in mw.findChildren(QtWidgets.QDockWidget)])
    it = QtCore.QDirIterator(":/", QtCore.QDirIterator.Subdirectories)
    res = []
    while it.hasNext():
        res.append(it.next())
    imgs = [p for p in res if p.lower().endswith((".svg", ".png"))]
    log(len(res), "resource,", len(imgs), "kép; első 100 kép:")
    for p in imgs[:100]:
        log(" ", p)


for step in (versions, paths, proxy_info, network_urllib, network_qt, plugin_state, layerstack, menu_actions):
    guard(step)

try:
    import substance_painter.application as _app
    _ver = _app.version()
except Exception:
    _ver = "unknown"
_path = os.path.join(tempfile.gettempdir(), f"spx_check_{_ver}.txt")
with open(_path, "w", encoding="utf-8") as fh:
    fh.write(OUT.getvalue())
print(OUT.getvalue()[:3000])
print("...\nTeljes riport:", _path)
