# Research: meglévő Painter menüparancsok és UI-gombok meghívása + ikonjaik elérése

Ticket: [#5](https://github.com/tamaslaszlototh/SPExtension/issues/5) · Map: [#1](https://github.com/tamaslaszlototh/SPExtension/issues/1)
Dátum: 2026-11-03 · Célverziók: Painter **11.1.0** és **12.2.0** (Windows)

## Kérdés

Meg tud-e hívni egy plugin **bármilyen** meglévő Painter-műveletet (menüparancs, pl. Save/Quick save; layer stack toolbar-gomb, pl. Add fill layer), hivatalos API-val vagy a főablak `QAction`-jeinek/widgetjeinek megkeresésével? Mennyire stabil ez 11.1 és 12.2 között? Elérhető-e programból a művelet **ikonja**? Felsorolhatók-e a meghívható műveletek?

## Röviden

1. **A hivatalos API-ban nincs olyan függvény, ami meglévő műveletet hívna meg vagy listázna.** A `substance_painter.ui` csak *hozzáadni* tud (saját `QAction` beszúrása egy előre definiált menübe, dock, toolbar). Nincs „run command by id” és nincs „list actions”.
2. **Sok művelethez van viszont hivatalos, *szemantikus* API**, ami a menüparancsot kiváltja: `project.save()` / `save_as()` / `save_as_copy()`, `layerstack.insert_fill()` / `insert_paint()` / `insert_group()` / …, `ScopedModification` az egy lépésben visszavonható módosításokhoz. Ezek dokumentáltak, és ezeket érdemes elsődlegesen használni.
3. **A főablak `QAction`-jei elérhetők és triggerelhetők** (`get_main_window()` egy `QMainWindow`, ezen működik a `findChildren(QAction)` és a `menuBar().actions()`). Ezt nem hivatalos API-ként működő gyakorlat igazolja (egy Adobe-munkatárs repója és a tik_manager4), és **verzióról verzióra törhet**.
4. **A layer stack panel gombjai (pl. Add fill layer) valószínűleg *nem* `QAction`-ök vagy `QWidget`-ek**, mert a Painter paneljei nagy részben QML-ben (Qt Quick) készülnek. Ezek a `findChildren` számára láthatatlanok. Ez **nem igazolt**, a Painterben ellenőrizni kell (lásd a lenti szkriptet).
5. **Ikon:** ha van `QAction`, akkor a `QAction.icon()` egy `QIcon`, ami `pixmap()`-pel kirajzolható a saját Buttonon. Ez Qt-szinten garantált. Hogy a Painter adott actionjeihez tényleg van-e (nem üres) ikon, azt dokumentum nem mondja meg, mérni kell. QML-gombok ikonjához nincs támogatott hozzáférés.
6. **Felsorolás:** a `findChildren(QAction)` eredményéből (szöveg, objectName, shortcut, ikon) a felhasználónak választható lista építhető. Nem hivatalos, a lista összetétele verziófüggő, a QML-alapú gombok pedig kimaradnak belőle.

## Igazolt tények (forrással)

### Hivatalos Painter Python API

| Tény | Forrás |
|---|---|
| `substance_painter.ui.get_main_window() -> PySide6.QtWidgets.QMainWindow`. | [ui module (Experience League)](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/ui) |
| A `ui` modul függvényei: `show_main_window`, `get_main_window`, `get/set/reset_layout`, `get_layout_mode`, `add_dock_widget`, `add_plugins_toolbar_widget`, `add_menu`, `add_toolbar`, `add_action`, `delete_ui_element`, `get_current_mode`, `switch_to_mode`. **Nincs köztük meglévő action meghívása vagy listázása.** | ugyanott |
| `add_action(menu: ApplicationMenu, action: QAction)`: saját actiont tesz egy előre definiált menübe, és **törli az action tooltipjét**. Az `ApplicationMenu` értékei: `File, Edit, Mode, Window, Viewport, Help`. | ugyanott |
| `add_dock_widget(widget, ui_modes)`: ha a widgetnek van window iconja, a Painter gyorsgombot tesz ki a dock újranyitásához. Egyedi `objectName` kell a layout mentéséhez. | ugyanott |
| `project.save(mode=ProjectSaveMode.Incremental)`, `save_as(path, mode)`, `save_as_copy(path, mode)`, `save_as_template(path, texture_set_name)`. `ProjectSaveMode` lehet `Full` vagy `Incremental`. `ProjectError`-t dob, ha nincs nyitott projekt vagy a Painter busy. Kiegészítők: `needs_saving()`, `is_busy()`, `execute_when_not_busy(callback)`, `file_path()`. **Külön „quick save” függvény nincs.** | [project module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/project) |
| A File menü dokumentált mentési parancsai: Save, Save as, Save as copy, Save and compact, Save as template. „Quick save” nevű menüpontot a dokumentáció nem említ. | [File menu (Experience League)](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/interface/main-menu/file-menu) |
| A Layerstack edition beszúró függvényei: `insert_paint`, `insert_fill`, `insert_generator_effect`, `insert_filter_effect`, `insert_levels_effect`, `insert_compare_mask_effect`, `insert_color_selection_effect`, `insert_group`, `instantiate`, `insert_anchor_point_effect`, `insert_smart_mask`, `insert_smart_material`, `delete_node`, pozíció: `InsertPosition.from_textureset_stack/above_node/below_node/inside_node`. | [Layerstack edition](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/edition) |
| `ScopedModification(name)`: „can be used to group many layerstack modification calls in a single undoable command”. Ez pontosan a map „egy Ctrl+Z” döntéséhez kell. | ugyanott |
| Az event modulban **nincs** esemény menü- vagy action-aktiválásra. A UI-hoz kötődő egyetlen esemény a `GraphicalUserInterfaceStarted`. Van `ProjectAboutToSave`, `ProjectSaved`, `LayerStacksModelDataChanged` stb. A `DISPATCHER.connect` gyenge referenciát tart, a `connect_strong` erőset. | [event module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/event) |
| `substance_painter.js.evaluate(js_code)`: kódot futtat a „legacy embedded JavaScript engine”-en. Ez kerülőút a régi JS API felé, a „legacy” jelző miatt nem ajánlott. | [js module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/js) |

### 11.1.0 és 12.2.0 közötti különbségek (hivatalos release notes és API changelog)

| Verzió | Releváns változás | Forrás |
|---|---|---|
| 11.0.1 | Qt frissítés egy újabb **6.5.x**-re, ez a 11.1 alapja. | [All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes) |
| 11.1.0 (API 0.3.5) | `ui` modult érintő változás nincs. Ismert hiba: „ghost widgets deleted by script still function”, vagyis a `delete_ui_element` után is működhetnek a widgetek. | All Changes; [API changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog) |
| 11.1.1 | Javítva: hiba a layer stack *ScopedModification-ön kívüli* szerkesztésekor. | All Changes |
| 12.0.0 | **Qt 6.8.6** és **Python 3.13**. A New project és a Project configuration ablakot átdolgozták. | All Changes |
| 12.0.2 (API 0.3.6) | Javítva: hiba csatorna hozzáadásakor ScopedModification-ön belül. A `project.create()` és a `reload_mesh()` explicit auto-unwrap paramétert kér. | All Changes; API changelog |
| 12.0.3 | Javítva: kilépéskor összeomlás a bent maradt Qt widgetek miatt, ami a plugin cleanup szempontjából fontos. | All Changes |
| 12.1.0 (API 0.3.7) | Geometry mask API bővült, a `ChannelType` OpenPBR neveket kapott. A baking toolbar és a mesh map lista átdolgozva, **új baking mode ikon**. | All Changes; API changelog |
| 12.2.0 (2026-10-21) | UI-változások: Cage Painting UI, blend mode a toolbarban, átcsoportosított display settings, reset stack opciók. Python API-változást a dokumentáció nem listáz. | All Changes |

Következmények:
- Mindkét verzió **Qt 6 / PySide6**, így a `QAction` mindkettőben a `PySide6.QtGui`-ban van (Qt 6.0 óta QtGui, korábban QtWidgets). Import-elágazás nem kell. ([QAction, Qt 6](https://doc.qt.io/qt-6/qaction.html): „Since: Qt 6.0”, `Qt6::Gui`)
- A `ui` modul API-ja 11.0 és 12.1 között a changelog szerint **nem változott**, így a hivatalos UI-hívások stabilak.
- A Qt-fa (menük, objectName-ek, action-szövegek, ikonok) belső implementáció. A release notes sorra hoz UI-átdolgozásokat (12.0 ablakok, 12.1 baking toolbar és ikon, 12.2 toolbar). **Ezek a nem hivatalos lookupokat bármikor eltörhetik.**

### Qt / PySide (elsődleges Qt-dokumentáció)

| Tény | Forrás |
|---|---|
| `QObject.findChildren()` alapértelmezésben **rekurzív** (`Qt::FindChildrenRecursively`). Az `objectName` alapból üres string. | [QObject](https://doc.qt.io/qt-6/qobject.html) |
| `QAction.trigger()`: „convenience slot that calls activate(Trigger)”. Az `associatedObjects()` megadja, mely menükhöz vagy toolbarokhoz van rendelve. A `text`, `iconText`, `icon` property olvasható. Letiltott action nem triggerelhető shortcuttal, és a felhasználó sem választhatja. | [QAction](https://doc.qt.io/qt-6/qaction.html) |
| `QIcon.pixmap(size, mode, state)` igény szerint generál pixmapet. Az `availableSizes()` a meglévő méreteket adja, az `isNull()` igaz, ha nincs se pixmap, se fájl. SVG-hez a QtSvg ikon-engine tetszőleges méretben rajzol újra. | [QIcon](https://doc.qt.io/qt-6/qicon.html) |
| A binárisba fordított Qt resource-ok induláskor automatikusan regisztrálódnak, és `:/` prefixszel érhetők el. A `QFile` és a `QDir` elfogad resource-útvonalat. | [Qt Resource System](https://doc.qt.io/qt-6/resources.html) |
| A `QQuickWidget` egy QML-jelenetet egyetlen widgetben jelenít meg. A `rootObject()` egy `QQuickItem`-et ad, ami **nem `QWidget`**, ezért a QML-elemek a `findChildren(QWidget/QAction)` számára nem láthatók. | [QQuickWidget](https://doc.qt.io/qt-6/qquickwidget.html) |

## Támogató bizonyíték (nem elsődleges forrás, community vagy harmadik fél)

- **[Támogató] Adobe-munkatárs (Vincent Gault) repója**, [`vg_painter_actions.py`](https://github.com/cgvinny/vg_painter_utilities/blob/main/modules/vg_pt_utils/vg_painter_actions.py): `ui.get_main_window().findChildren(QtGui.QAction)`, szöveg szerinti szűrés, majd `.trigger()`. A docstring szerint: *„These actions are not part of the official substance_painter Python API … subject to change across Painter versions. Use with caution.”* 2026 áprilisi (12.0.x-es) szkennelés alapján triggerelhető actionök például: „Apply default brush”, „Bake All Texture Sets”, a módváltók (Painting F9, Rendering F10, Bake F8), „Pause Engine Computation” és a panel-toggle-ök (Layers, Tools, Assets, Brushes, Texture Set Settings…). **Nem található QAction-ként:** stencil ki/be és a brush-tulajdonságok. Ugyanez a repó a `findChildren(QAction)` + `shortcuts()` párossal térképezi fel a Painter összes shortcutját ([`vg_settings_dialog.py`](https://github.com/cgvinny/vg_painter_utilities/blob/main/modules/vg_pt_utils/vg_settings_dialog.py)).
- **[Támogató] tik_manager4**, [`dcc/substance/utils.py`](https://github.com/masqu3rad3/tik_manager4/blob/dev/tik_manager4/dcc/substance/utils.py): `main_window.menuBar().actions()`, majd a `menu.objectName() == "file"` menüben az az action, amelynek `shortcut() == QKeySequence.Save`, végül `.trigger()` ([`main.py`](https://github.com/masqu3rad3/tik_manager4/blob/dev/tik_manager4/dcc/substance/main.py)). Ebből látszik, hogy a File menünek van stabil-szerű `objectName`-je (`"file"`). A shortcut szerinti keresés viszont törik, ha a felhasználó átkötötte a Ctrl+S-t.
- **[Támogató] Tech-Artists fórum** ([thread](https://www.tech-artists.org/t/substance-painter-python-api/16176)): saját menühöz a `get_main_window().menuBar().addMenu()` működött a felhasználónak, az `add_menu()` nem.
- **[Támogató] Adobe Community** ([thread](https://community.adobe.com/questions-59/how-to-match-qpushbutton-size-to-default-plugin-toolbar-icons-using-add-plugins-toolbar-widget-629841)): a plugin toolbarba `QToolButton` illik vizuálisan, nem `QPushButton`.

## Bizonytalan pontok (ellenőrizni kell a Painterben)

1. **QML vagy widget a layer stack panelben?** Nem találtam elsődleges forrást arra, hogy a Layers panel (és benne az „Add fill layer” gomb) QML-ben készül. A JS plugin-rendszer és az Adobe saját pluginjai QML-t használnak ([Creating a JavaScript plugin](https://helpx.adobe.com/substance-3d-painter/scripting-and-development/scripts-and-plugins/creating-a-javascript-plugin.html); [AllegorithmicSAS QML példa](https://github.com/AllegorithmicSAS/painter-plugin-resources-updater/blob/master/ResourceUpdaterWindow.qml)), és a Vincent Gault-féle szkennelés szerint több panelfunkció hiányzik a QAction-fából. Ez erős, de közvetett jel. Ha QML, akkor a gombot csak a `QQuickWidget.rootObject()` alatti `QQuickItem`-ek bejárásával és szintetikus egér-eseménnyel lehetne „megnyomni”. Ez nagyon törékeny, nem javasolt.
2. **Van-e ikon a Painter QAction-jein?** A menüben megjelenő ikon mellett az action lehet ikon nélküli is (`icon().isNull()`). Nem dokumentált, hogy melyik actionnek van ikonja. Mérni kell mindkét verzión.
3. **Lazy menük:** egyes almenük (pl. Open recent) tartalma tipikusan csak `aboutToShow`-kor töltődik fel, így a felsorolás nem teljes, amíg a menü nem nyílt meg. Ez általános Qt-minta, a Painterre nem igazolt.
4. **Azonosítás:** az `objectName` lehet üres (Qt-alapértelmezés). A `text()` lokalizálódhat (ha a Painter UI-nyelve nem angol), a shortcut átköthető. Stabil kulcsnak az `objectName` a legjobb, ha van. Ha nincs, akkor a menü-útvonal és a szöveg együtt, angol UI-t feltételezve.
5. **Qt resource-ok listázása (`QDirIterator(":/")`)**: elvben a Painter binárisába fordított ikonok is olvashatók ugyanabból a processzből. Hogy a Painter ilyen formában tárolja-e az ikonjait, és milyen útvonalon, nem dokumentált. A telepítési mappa ikonfájljairól sem találtam forrást.
6. **12.2.0 Python API:** az API changelog utolsó bejegyzése 0.3.7 (Painter 12.1.0). Ha a 12.2 hozott API-változást, azt a dokumentáció még nem tartalmazza.

### Ellenőrző szkript (mindkét gépen a Painter Python konzoljában futtatandó)

```python
from PySide6 import QtGui, QtWidgets, QtQuickWidgets, QtCore
import substance_painter.ui as ui

mw = ui.get_main_window()
rows = []
for a in mw.findChildren(QtGui.QAction):
    owners = [o.objectName() or type(o).__name__ for o in a.associatedObjects()]
    rows.append((a.objectName(), a.text().replace("&", ""), a.shortcut().toString(),
                 not a.icon().isNull(), a.icon().availableSizes(), a.isEnabled(), owners))
print(len(rows), "QAction")
for r in sorted(rows, key=lambda r: r[1]):
    print(r)

print([ (m.objectName(), m.title()) for m in mw.menuBar().findChildren(QtWidgets.QMenu) ])
print("QQuickWidgets:", [ (w.objectName(), w.source().toString()) for w in mw.findChildren(QtQuickWidgets.QQuickWidget) ])

it = QtCore.QDirIterator(":/", QtCore.QDirIterator.Subdirectories)
res = []
while it.hasNext():
    res.append(it.next())
print(len(res), "resource;", [p for p in res if p.endswith((".svg", ".png"))][:50])
```

Ha a `QQuickWidgets` lista nem üres, és benne van a layer stack (`source` URL), akkor az 1. pont igazolódott.

## Javaslat a spec számára

- **Menu button**: két forrás kell. (a) **Kurált lista** azokról a műveletekről, amelyekhez van hivatalos API (Save → `project.save()`, Add fill/paint layer/group → `layerstack.insert_*` + `ScopedModification`). Ezek stabilak, és Workflow Step-ként is visszavonhatók. (b) **Opcionális „haladó” lista**: futásidőben a `findChildren(QAction)`-ből, a ténylegesen talált actionökkel. A tárolt kulcs lehetőleg `objectName`, ennek hiányában menü-útvonal és szöveg. Ha nem található, a Button „hiányzó” állapotot mutat (ugyanaz a minta, mint a „hiányzó erőforrás” kérdésnél).
- **Ikon**: QAction-alapú gombnál a `QAction.icon()`, ha nem `isNull()`. A hivatalos API-s műveleteknél (pl. insert_fill) az ikon nem kérhető le, mert a layer stack gombja nem QAction (valószínűleg QML). Ide a pluginnal szállított saját ikon kell, vagy egy QAction-ikon, ha az ellenőrző szkript talál ilyet. **Ez ütközik a map döntésével** („automatikusan a Painter által használt ikon”), ezért a döntést a mérés után pontosítani kell.
- **Kompatibilitás**: a hivatalos API-részhez 11.1 és 12.2 között nem kell verzióelágazás. A Qt-fa lookup verziónként eltérhet, ezért defenzíven kell írni: nincs találat = nincs Button, nem kivétel.
