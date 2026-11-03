# Research: Panel dockolás és plugin-életciklus a Painter API-ban (11.1 vs 12.2)

Ticket: [#2](https://github.com/tamaslaszlototh/SPExtension/issues/2) · Térkép: [#1](https://github.com/tamaslaszlototh/SPExtension/issues/1) · Kutatás dátuma: 2026-11-03

## Kérdés

Hogyan hoz létre egy Python plugin lebegő/dockolható Panelt a Substance 3D Painter **11.1.0** és **12.2.0** verziójában? Érintett témák: `substance_painter.ui` dock API, a plugin start/close életciklusa, a Panel pozíciójának megmaradása újraindítás után, a Qt/PySide verzió mindkét Painterben, és minden API-különbség, ami a pluginra hat.

## Röviden

- A Panel létrehozása mindkét verzióban ugyanaz: egy saját `QWidget`-et átadunk a `substance_painter.ui.add_dock_widget(widget, ui_modes=UIMode.Edition)` hívásnak, ami egy `QDockWidget`-et ad vissza. Ez a widget lebegtethető és dockolható.
- Ha a widgetnek **egyedi `objectName`-je** van, a Painter ez alapján menti és állítja vissza a dock helyét és méretét. Ha nincs (a hivatalos hello-plugin példában sincs), a pozíció nem tud megmaradni.
- Életciklus: a `plugins/` mappában lévő modulnak `start_plugin()` és `close_plugin()` függvénye van. A `close_plugin()`-ben minden hozzáadott UI elemet `substance_painter.ui.delete_ui_element()`-tel törölni kell.
- Mindkét verzió **PySide6 / Qt6**. A 11.1 Qt 6.5.x-et (valószínűleg 6.5.8-at) és Python 3.11-et használ, a 12.x Qt 6.8.6-ot és Python 3.13-at. A PySide2→PySide6 törés a 10.1-ben volt, így a két célverzió között nincs.
- A **`substance_painter.ui` modulban nincs dokumentált változás** 11.1 (API 0.3.5) és 12.2 között. A changelog 0.3.0 óta egyszer sem említi a `ui`-t, a plugin modult vagy a Qt-t.
- A plugint érintő eltérések a stabilitási hibajavítások: a 11.x-ben ismert hiba a "ghost widget" (a script által törölt widget látszik és működik tovább). A 12.0.3 javította a "crash on exit with leftover Qt widgets" hibát. A 11.1.0 tehát érzékenyebb a nem rendesen takarított widgetekre.

## Ellenőrzött tények

### 1. Dock widget API (`substance_painter.ui`)

Forrás: [substance_painter.ui modul (Experience League)](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/ui). A régi helpx URL ([helpx ui.html](https://helpx.adobe.com/substance-3d-painter-python/api/substance-painter/ui.html)) ugyanezt a tartalmat hordozza, de botvédelem miatt automatán nem olvasható.

- `add_dock_widget(widget: PySide6.QtWidgets.QWidget, ui_modes: int = UIMode.Edition) -> PySide6.QtWidgets.QDockWidget`
  - A widgetet dockként a főablakba teszi, és visszaadja a létrejött `QDockWidget`-et.
  - Ha a widgetnek van `windowIcon`-ja, abból gyorsgomb lesz, amivel a bezárt dock újranyitható.
  - Ha a widgetnek **egyedi `objectName`-je** van, ez alapján menti és állítja vissza a dock helyét és geometriáját.
  - `ui_modes`: `UIMode` flagek kombinációja, ez szabja meg, melyik módban (Edition / Visualisation / Baking) látszik a dock.
  - `ServiceNotFoundError`-t dob, ha a UI service még nem indult el.
- `delete_ui_element(element: QWidget)`: törli a UI elemet. Utána bármilyen metódushívás rajta kivételt dob.
- `UIMode`: `Edition = 1`, `Visualisation = 2` (Iray), `Baking = 4`. Bitflagek, tehát `UIMode.Edition | UIMode.Baking` is megadható.
- Layout függvények: `get_layout(mode) -> bytes`, `set_layout(layout: bytes) -> UIMode`, `get_layout_mode(layout) -> UIMode`, `reset_layout(mode)`. Ezekkel a teljes főablak-layout menthető vagy visszaállítható módonként.
- Egyéb: `get_main_window() -> QMainWindow`, `show_main_window()`, `add_plugins_toolbar_widget(widget)`, `add_toolbar(title, object_name, ui_modes) -> QToolBar` (itt is egyedi object name kell a layout-mentéshez), `add_menu(menu)`, `add_action(ApplicationMenu, QAction)`, `get_current_mode()`, `switch_to_mode(mode)`.
- A layout függvények a 0.2.7-ben (Painter 8.2.0), a `get_current_mode` / `switch_to_mode` / `UIMode.Baking` a 0.2.8-ban (Painter 8.3.0) jelentek meg ([Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog)). Mindkét célverzióban megvannak.

### 2. Pozíció/állapot megmaradása, Qt oldalról

Forrás: [Qt 6 QMainWindow docs](https://doc.qt.io/qt-6/qmainwindow.html).

- `saveState()`: "The objectName property is used to identify each QToolBar and QDockWidget." Egyedinek kell lennie.
- `restoreDockWidget()`: "Restores the state of dockwidget if it is created after the call to restoreState()." Egy plugin dockja a Painter layout-visszaállítása **után** jön létre, ezért a visszaállítás ezen a mechanizmuson múlik. A Painter `add_dock_widget` doksija szerint az `objectName` alapján ezt megteszi.

### 3. Plugin életciklus (`substance_painter_plugins`)

Források: [substance_painter_plugins modul](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/writing-plugins/substance-painter-plugins), [Hello Plugin példa](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/examples/hello-plugin), [Plugins menu](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/interface/main-menu/plugins-menu), [Load external Python plugins](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/load-external-python-plugins), [Create a Python plugin](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/create-a-python-plugin).

- Egy plugin-gyökérben három almappa van, mindhárom bekerül a `sys.path`-ba:
  - `plugins/`: opcionális, igény szerint indított modulok, `start_plugin()`-nal.
  - `startup/`: minden induláskor betöltött modulok.
  - `modules/`: közös segédmodulok.
  - Ha egy modul a `plugins/` és a `startup/` mappában is megvan, a `plugins/` nyer. Más nevű mappákban lévő scripteket a Painter figyelmen kívül hagyja.
- Keresési út: `substance_painter_plugins.path`. Forrásai a `SUBSTANCE_PAINTER_PLUGINS_PATH` környezeti változó, a telepítési könyvtár és a felhasználói erőforrás-könyvtár. Változtatás után `update_sys_path()`-t kell hívni.
- Windowson a felhasználói mappa (7.2+): `C:\Users\<user>\Documents\Adobe\Adobe Substance 3D Painter`. A Python pluginok a `python\plugins` alá kerülnek (a sima `plugins` mappa a JavaScript pluginoké). Ez a Dokumentumok mappa, ezért **admin jog nélkül is írható**, ami a barát 12.2-es gépe miatt fontos. (A pontos `python\plugins` útvonalat a tutorial csak elszórtan írja le; az összerakás következtetés.)
- API: `start_plugin(module)`, `close_plugin(module, gc_collect=True)`, `is_plugin_started(module)`, `reload_plugin(module)` (close, opcionálisan a modul saját `reload_plugin`-ja, majd start; az `importlib.reload` korlátai érvényesek), `plugin_module_names()`, `startup_module_names()`, `load_startup_modules()`, `close_all_plugins()`, a `plugins` dict.
- A Python menüben minden pluginnak van Disable/Enable, Reload, Configure és About pontja. A Painter az induláskor betöltött pluginokat listázza.
- Hivatalos minta (Hello Plugin, PySide6): egy globális `plugin_widgets` listába gyűjti a hozzáadott widgeteket. A `start_plugin()` `add_dock_widget`-tel hozzáadja őket, a `close_plugin()` mindegyikre `delete_ui_element`-et hív, aztán kiüríti a listát.

### 4. Qt / PySide / Python verziók

Források: [10.1 release notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/old-versions/version-10-1), [All changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes), [12.0 release notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/version-12-0), [Qt6 migration guide](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/qt6-migration).

| Painter | Qt | PySide | Python | Python API |
|---|---|---|---|---|
| 10.1.0 | 6.5.6 | PySide6 6.5.6 | 3.11 | 0.3.2 |
| 11.0.1 | "Update to Qt 6.5.8" | (nem írják) | 3.11 | 0.3.4 |
| **11.1.0** (2025-11-18) | 6.5.8 (következtetés, lásd lent) | PySide6 | 3.11 (következtetés) | **0.3.5** |
| 12.0.0 (2026-03-09) | "Update Qt to 6.8.6" | PySide6 (verzió nincs megadva) | "Update Python to 3.13" | – |
| 12.0.2 | | | | 0.3.6 |
| 12.1.0 | | | | 0.3.7 |
| **12.2.0** (2026-10-21) | 6.8.6 (következtetés) | PySide6 | 3.13 (következtetés) | 0.3.7 (nincs újabb changelog-bejegyzés) |

- A Qt5→Qt6 (PySide2→PySide6) váltás a **10.1**-ben történt, mindkét célverzió azon túl van. A migrációs guide törései (`QAction` a `QtGui`-ban, `exec()` az `exec_()` helyett, `|` a `+` helyett a billentyű-kombinációknál, `setContentsMargins` a `setMargin` helyett) **csak 10.1 előtti Painterhez** számítanak.
- Vigyázat: a hivatalos ["Create a Python plugin"](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/create-a-python-plugin) tutorial még `QtWidgets.QAction`-t használ (PySide2 stílus), ez PySide6-on hibát ad. Helyesen: `QtGui.QAction`.

### 5. API-különbségek 11.1.0 (API 0.3.5) és 12.2.0 (API 0.3.7) között

Forrás: [Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog).

- **0.3.6 (12.0.2)**: `project.AutoUnwrapUVTilesSettings`. A `project.create()` / `project.reload_mesh()` auto-unwrap beállítást kap, és ezt **explicit meg kell adni** (már nem a preferenciákból jön). Új: `layerstack.export_as_smart_material()`, `export_as_smart_mask()`.
- **0.3.7 (12.1.0)**: a `textureset.ChannelType` alapértelmezésben OpenPBR csatornaneveket ad, a régi nevek aliasként megmaradnak. Új `LayerNode.get_geometry_mask()` / `set_geometry_mask()`; három régi geometry-mask setter deprecated.
- A `ui`, `substance_painter_plugins` és `event` modulban **nincs változás** a két verzió között. A 0.3.0 óta egyetlen `event`-bejegyzés van (`ReloadResourcesStarted/Ended`, 0.3.4 / 11.0), ez mindkét célverzióban megvan.
- Következmény a Panelre: a dock/életciklus kód verzióelágazás nélkül mehet. Elágazás (`substance_painter.application.version_info()`) csak akkor kell, ha egy Step/Workflow a fenti 12.x-es API-kat (pl. `export_as_smart_material`, `set_geometry_mask`) vagy az új `ChannelType` neveket használja.

### 6. Ismert hibák, amik a Panelt érintik

Forrás: [11.1 release notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/version-11-1), [All changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes).

- 10.1.0 – 11.1.x, ismert hiba: "[Python] Ghost widget appears deleted by script still functioning". 12.x-ben már nincs a listán.
- 12.0.3 (2026-05-05) javítás: "[Python] Painter crash on exit with leftover Qt widgets". A **11.1.0 ezt a javítást nem kapta meg**. A barát 12.2-je igen.

## Bizonytalan / nem dokumentált pontok

- **A 11.1.0 pontos Qt és Python verziója.** Az "All changes" lap 11.0.1 és 12.0.0 között nem jelez Qt- vagy Python-frissítést, így 6.5.8 és 3.11 a valószínű. Kiderül futás közben: `PySide6.__version__`, `PySide6.QtCore.qVersion()`, `sys.version`.
- **A PySide6 pontos verziója 12.x-ben** nincs leírva (Qt 6.8.6 mellett valószínűleg PySide6 6.8.x). Ezt is futás közben kell ellenőrizni.
- **Megmarad-e a plugin Enable állapota újraindítás után?** A docs nem mondja meg. Ha a Panelnek mindig indulnia kell, a biztos út a `startup/` mappa (azt minden induláskor betölti), vagy egy kis `startup/` modul, ami `substance_painter_plugins.start_plugin()`-nal elindítja a fő plugint. Kézzel ellenőrizni kell.
- **Lebegő állapot visszaállítása.** A docs "location and geometry" mentést ígér. Hogy ebbe a floating állapot és a lebegő ablak monitorpozíciója is beletartozik-e, nincs leírva. Valószínű, hiszen a `QMainWindow::saveState` ezt is tárolja, de tesztelni kell.
- **Mi történik a dockkal plugin-reloadkor és kikapcsoláskor?** Hogy a `delete_ui_element` a `QDockWidget`-et vagy a belső widgetet kapja, nincs részletezve. A hivatalos példa a belső widgetet adja át (azt, amit `add_dock_widget`-nek adott). A 11.x ghost widget hibája miatt ezt 11.1.0-n külön tesztelni kell.
- **Az API docs csak a legfrissebb verziót mutatja.** Verziónkénti archivált `ui` oldalt nem találtam. A "nincs változás" állítás a changelogon alapul, nem két doc-verzió összevetésén.
- **A régi helpx.adobe.com oldalak** botvédelem miatt (HTTP 403) nem voltak olvashatók. Minden hivatkozott tartalom az Experience League tükörről és a Qt dokumentációból származik.

## Javasolt váz (következtetés a fentiekből, nem forrásból)

```python
# python/plugins/sp_panel/__init__.py
from PySide6 import QtWidgets
import substance_painter.ui as ui

_widgets = []

def start_plugin():
    panel = QtWidgets.QWidget()
    panel.setObjectName("spextension.panel")   # egyedi -> pozíció mentése
    panel.setWindowTitle("SPExtension")
    # panel.setWindowIcon(...)                 # gyorsgomb az újranyitáshoz
    dock = ui.add_dock_widget(panel, ui.UIMode.Edition)
    _widgets.append(panel)

def close_plugin():
    for w in _widgets:
        ui.delete_ui_element(w)
    _widgets.clear()
```
