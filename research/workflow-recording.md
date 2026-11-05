# Research: Workflow rögzítése a layer stack változásainak figyelésével

Ticket: [#17](https://github.com/tamaslaszlototh/SPExtension/issues/17) · Map: [#1](https://github.com/tamaslaszlototh/SPExtension/issues/1) · Step-katalógus: [#7](https://github.com/tamaslaszlototh/SPExtension/issues/7) · Kutatás dátuma: 2026-11-05
Célverziók: Painter **11.1.0** (Python API 0.3.5, Python 3.11, Qt 6.5) és **12.2.0** (API 0.3.7, Python 3.13, Qt 6.8), Windows.

Előzmények: [research/layerstack-ops.md](https://github.com/tamaslaszlototh/SPExtension/blob/research/layerstack-ops/research/layerstack-ops.md) (#4), [research/menu-actions-icons.md](https://github.com/tamaslaszlototh/SPExtension/blob/research/menu-actions-icons/research/menu-actions-icons.md) (#5), [research/brush-preset.md](https://github.com/tamaslaszlototh/SPExtension/blob/research/brush-preset/research/brush-preset.md) (#3).

## Kérdés

Megvalósítható-e a Workflow **rögzítése** (Recording), ha a History/undo lista nem olvasható az API-ból? Van-e layer stack változás-esemény, kikövetkeztethetők-e a v1 Step-ek két snapshot diffjéből (a beszúrt resource-szal együtt), rögzíthetők-e a menüparancsok a QAction `triggered` jeléből, észlelhető-e a brush-váltás, és mi zavarja a diffet?

## Röviden (ítéletek)

| # | Kérdés | Ítélet | Bizonyosság |
|---|---|---|---|
| 1 | Van-e layer stack változás-esemény? | **Igen:** `substance_painter.event.LayerStacksModelDataChanged`. **Nincs payloadja** (nem mondja meg, mi változott), a gyakorisága és a kiváltó okai nem dokumentáltak. Diffhez elég „ébresztőnek”. | Létezés: ellenőrzött (hivatalos doc + Adobe példák). Gyakoriság: **mérni kell** |
| 2 | Kikövetkeztethetők-e a katalógus Step-jei snapshot-diffből? | **Igen, nagyrészt.** Fill/Paint/Folder, fekete/fehér maszk, Generator/Filter/Levels/Anchor point, blend mode, opacity az API-ból teljesen kiolvasható (`uid`, `get_type`, `get_parent`, sorrend, `has_mask`/`get_mask_background`, `get_blending_mode`/`get_opacity`, `content_effects`/`mask_effects`). Generator/Filter resource: **igen**, `get_source().resource_id`. | Ellenőrzött API; az esemény időzítése mérendő |
| 2b | Smart material / Smart mask resource azonosítása | **Csak heurisztikával.** A beszúrt csoport/effektek nem hivatkoznak vissza a smart material/mask resource-ra. Smart material: csoportnév → `resource.search` név szerint (átnevezésnél, névütközésnél bukik). Smart mask: csak „több maszk-effekt egyszerre jelent meg” mintázat → a Recording végén a felhasználó választja ki a listából. | Ellenőrzött hiány (nincs getter); a heurisztika mérendő |
| 3 | Menüparancs rögzítése QAction `triggered`-ből | **Igen, menüből és shortcutból.** A `triggered` a felhasználói aktiváláskor és `trigger()` hívásakor is tüzel, ezért a plugin saját hívásait egy re-entrancy flaggel kell kiszűrni (a `trigger()` szinkron). A QML-gombok (pl. layer stack toolbar) nem QAction-ök, azok nem jönnek át, de ezeket a layer stack diff úgyis látja. | Qt-oldal ellenőrzött; Painter-oldal mérendő |
| 4 | Brush/tool preset váltás észlelése | **Preset-váltásra nincs jel** (nincs tool/brush modul, nincs esemény). **Tool-váltásra lehet gyenge, nem hivatalos jel** (a Properties dock címe, pl. „Properties - Paint”; a tool-shortcutok QAction-jei). Tartalék: **Brush Step kézzel** a lista végére a Recording utáni szerkesztőben. | Hiány ellenőrzött; a tool-jel mérendő |
| 5 | Mi zavarja a diffet? | Festés (esemény-zaj, de a szerkezet nem változik), csúszkahúzás (sok köztes opacity-érték → összevonás), undo közben (a diff „visszafelé” lépést lát → az Undo QAction figyelésével vagy a „pontos visszafordítás” felismerésével kezelhető), texture set váltás (snapshot texture setenként), projektváltás (Recording leáll), drag-and-drop átrendezés és törlés (nem katalógus-Step → „kimaradt” jelzés). | Részben ellenőrzött; mértékük mérendő |

**Összesített ítélet: a Recording megvalósítható** 11.1.0-n és 12.2.0-n azonos kóddal, „snapshot + diff, eseményre ébresztve” módszerrel, a v1 katalógus layer-részére megbízhatóan, a Smart material/mask resource-ra és a brushra tartalékkal (felhasználói választás a Recording végén). Előtte egy rövid mérés kell a barát gépein (lásd a lenti szkriptet és a prototype ticketet).

## Verziótábla (11.1.0 vs 12.2.0)

| Elem | 11.1.0 (API 0.3.5) | 12.2.0 (API 0.3.7) | Forrás / megjegyzés |
|---|---|---|---|
| `event.LayerStacksModelDataChanged` | ✅ (várhatóan) | ✅ | A [event modul](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/event) tartalmazza. A [changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog) **nem rögzíti, mikor került be**. Az Adobe [blending_mode példája](https://github.com/AdobeDocs/painter-python-api/blob/main/src/pages/guides/examples/blending_mode.md) Qt5/Qt6-elágazással (< 10.1) használja, tehát legalább 10.x óta létezik. A szkript `hasattr`-ral ellenőrzi. |
| Az esemény payloadja | nincs | nincs | [LumaPictures cg-stubs](https://github.com/LumaPictures/cg-stubs/blob/master/substance_painter/stubs/substance_painter-stubs/event.pyi): `class LayerStacksModelDataChanged(Event): ...` (mező nélküli frozen dataclass). Harmadik fél, de a stub a modulból generált. |
| `ProjectEditionEntered/Left`, `ProjectAboutToClose`, `ProjectOpened` | ✅ | ✅ | event modul |
| `TextureStateEvent` (festés közben, ≥ 500 ms throttling) | ✅ | ✅ | 0.2.7 / 0.2.9, event modul |
| Navigáció, típus, uid, mask, blend/opacity getterek | ✅ | ✅ | 0.3.0 óta, [navigation](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/navigation) |
| `GeneratorEffectNode/FilterEffectNode.get_source()` → `SourceSubstance.resource_id` | ✅ | ✅ | [generator](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/generator), [SourceSubstance](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/source-module/substance) |
| Smart material/mask → resource visszakeresése | ❌ | ❌ | [smartmaterial](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/smartmaterial), [smartmask](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/smartmask): nincs getter |
| `get_geometry_mask()` (snapshotban nem kell) | ❌ | ✅ | 0.3.7; a v1 katalógus nem használja |
| History / undo olvasása, undo-esemény | ❌ | ❌ | Nincs ilyen függvény/esemény; lásd #4 kutatás |
| Aktív tool/brush preset olvasása, váltás-esemény | ❌ | ❌ | Nincs tool modul ([module index](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/module-index)); lásd #3 kutatás |
| `QAction` a `PySide6.QtGui`-ban, `triggered` jel | ✅ (Qt 6.5) | ✅ (Qt 6.8) | [QAction](https://doc.qt.io/qt-6/qaction.html) |
| 12.1.0: „[History] Update "value" Undo entry wording to reflect parameter name” | – | ✅ | [All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes). Csak a History-szöveget érinti; ha a History dock modellje olvasható (lásd lent), a két verzió szövegei eltérnek. |

## 1. A layer stack változás-esemény

Hivatalos doc ([event modul](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/event)):

- `LayerStacksModelDataChanged`: „Event triggered when the status of the Layer Stacks changes” (tartalmilag; a doc példája a callbackben az aktív stack kijelölt node-jait olvassa).
- Feliratkozás: `event.DISPATCHER.connect(cls, cb)` (gyenge referencia, a callback garbage collectionnél lekapcsol), `connect_strong(cls, cb)`, `disconnect(cls, cb)`.
- A doc **nem mondja meg**, melyik szálon, milyen gyakran, és milyen műveletekre tüzel. Payload nincs (lásd stub).
- Projektbetöltés aszinkron: `ProjectOpened` előbb jöhet, mint hogy a projekt kész lenne, ezért `ProjectEditionEntered` után szabad olvasni (event doc). Az Adobe [save_selection példa](https://github.com/AdobeDocs/painter-python-api/blob/main/src/pages/guides/examples/save_selection.md) ugyanezt csinálja (`is_in_edition_state()` + saját „ready” flag, „because of concurrency between events”).

Mit mutatnak a példák (nem elsődleges forrás a viselkedésre, de jelzés):

- Az Adobe [save_selection](https://github.com/AdobeDocs/painter-python-api/blob/main/src/pages/guides/examples/save_selection.md) és [blending_mode](https://github.com/AdobeDocs/painter-python-api/blob/main/src/pages/guides/examples/blending_mode.md) példa erre az eseményre építi a **kijelölés-követést**, és a callbackben Qt widgeteket épít át. Ebből következik: (a) a kijelölés változása várhatóan kivált eseményt, (b) a callback a főszálon (GUI-szál) fut.
- Egy Adobe-munkatárs pluginja ([vg_channel_overlay.py](https://github.com/cgvinny/vg_painter_utilities/blob/main/modules/vg_pt_utils/vg_channel_overlay.py)) ezt írja: „LayerStacksModelDataChanged may not fire on a bare selection click”, és 500 ms-os pollinggal egészíti ki. **Ellentmond** az Adobe példák feltevésének → mérni kell.

**Következmény a tervre:** az eseményt csak „valami változott” jelzésnek kell tekinteni. Minden eseményre `QTimer.singleShot(~100–200 ms)` debounce, utána teljes snapshot az aktív stackről és diff az előzőhöz. Biztonsági hálónak egy lassú (pl. 500 ms–1 s) polling a Recording alatt, ha a mérés kihagyott eseményeket mutat. A callbackben **tilos** a layer stacket módosítani (rekurzív esemény).

## 2. Step-ek kikövetkeztetése snapshot-diffből

Snapshot node-onként (mind dokumentált getter, [navigation](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/navigation)): `uid()`, `get_type()` (`NodeType`: PaintLayer, FillLayer, GroupLayer, InstanceLayer, PaintEffect, FillEffect, GeneratorEffect, FilterEffect, LevelsEffect, CompareMaskEffect, ColorSelectionEffect, AnchorPointEffect), `get_name()`, szülő (`get_parent()`), pozíció (a szülőn belüli sorrend), `has_mask()` + `get_mask_background()`, `content_effects()` / `mask_effects()`, `get_blending_mode(ch)` / `get_opacity(ch)` csatornánként (maszk-stackben `channel=None`), `has_blending()`. Kijelölés: `get_selected_nodes(stack)`.

| v1 Step | Diff-mintázat | Resource | Ítélet |
|---|---|---|---|
| Fill / Paint / Folder hozzáadása (opc. név) | Új uid, típus FillLayer/PaintLayer/GroupLayer, layer-szinten. Pozíció: közvetlenül az előző current layer **fölött**, ugyanabban a szülőben → katalógus-Step; máshol → jelzés („nem a current layer fölé került”). A név akkor rögzítendő, ha eltér az alapértelmezettől (a következő snapshotban is figyelni kell az átnevezést). | – | ✅ |
| Fekete / fehér maszk | `has_mask` False→True, `get_mask_background()` Black/White. | – | ✅ |
| Generator | Új GeneratorEffect a `mask_effects()`-ben vagy `content_effects()`-ben. A UI-ban jellemzően előbb üres generator jön létre, utána választ a felhasználó → a Step „függőben” marad, és a `get_source()` (None → `SourceSubstance`) változásakor a `resource_id`-t beírjuk. | `get_source().resource_id` → `ResourceID` (`url()`) | ✅ |
| Filter | Ugyanígy, FilterEffect. | ugyanígy | ✅ |
| Levels / Anchor point | Új LevelsEffect / AnchorPointEffect. | – | ✅ |
| Blend mode (minden csatornára) | `get_blending_mode(ch)` változás. Ha csak egy csatornán változott (a UI csatornánként állít), a Step „minden csatornára” lesz, jelzéssel. | – | ✅ (csatorna-eltéréssel) |
| Opacity (0–100) | `get_opacity(ch)` változás; csúszkahúzásnál sok köztes érték → az azonos node+tulajdonság egymás utáni változásait egy Step-be vonjuk (az utolsó érték). | – | ✅ |
| Smart material | Új GroupLayer, amelynek már az első snapshotban vannak al-layerei (`insert_smart_material` is `GroupLayerNode`-ot ad). | **Nincs getter.** Heurisztika: a csoport neve = a smart material neve (nem dokumentált) → `resource.search(...)` név szerint, smart material usage-re szűrve. Több vagy nulla találat → a felhasználó választ. | ⚠️ heurisztika |
| Smart mask | Több új maszk-effekt egyszerre (az `insert_smart_mask` is effekt-listát ad); esetleg új maszk is. | **Nincs getter.** Az effekt-nevekből nem következtethető biztosan. → „Smart mask (válassz)” Step, a Recording végén a felhasználó választja ki. | ⚠️ kézi kiegészítés |

Nem katalógus-Step, de a diff észleli → „kimaradt” jelzés a Recording végén: törlés, átrendezés (drag), átnevezés meglévő layeren, láthatóság, fill tartalma (szín/anyag), instance, Compare mask / Color selection effekt, maszk eltávolítása.

Uid-ok: a doc szerint „Each node is identified by a node uid”, rossz uid-ra `ValueError`. **Nem dokumentált**, hogy az uid undo/redo után megmarad-e (mérendő), ez az undo-kezelésnél számít.

## 3. Menüparancs rögzítése QAction `triggered`-ből

- A [QAction](https://doc.qt.io/qt-6/qaction.html) `triggered(bool checked)` jele akkor jön, amikor a felhasználó aktiválja az actiont (menü, toolbar, shortcut), illetve `trigger()` hívásakor („convenience slot that calls activate(Trigger)”). `setChecked()`/`toggle()` nem váltja ki.
- A főablak QAction-jei elérhetők: `ui.get_main_window().findChildren(QtGui.QAction)` (#5 kutatás; nem hivatalos API, verziófüggő).
- **Saját kattintások kiszűrése:** a plugin minden saját `trigger()`-ét egy `self._replaying = True` flag között hívja; a `trigger()` szinkron, így a `triggered` ugyanabban a hívásban, a flag alatt érkezik → kiszűrhető. A Recording alatt a Panel többi gombja eleve letiltható.
- **Zaj:** a panel-toggle és mode-váltó actionök (Layers, Assets, F9/F10…) is QAction-ök → csak azokat rögzítsük, amelyek a Menu button által is választhatók (objectName alapján, #7 döntés szerint); a többit „kimaradt”-ként jelezzük.
- **Undo/Redo:** ha az Edit > Undo QAction (Ctrl+Z) létezik és a shortcut rajta fut, a `triggered` figyelésével az undo **észlelhető** → a Recording az utolsó rögzített Step-et visszavonhatja. Mérendő.
- **Később létrejövő actionök** (lazy menük): a Recording indulásakor gyűjtsük be az actionöket; a hiányzók nem rögzülnek. Kiegészítésként a `QMenu.triggered(QAction*)` jel a menük szintjén is elkapja a lazy almenük actionjeit.
- A layer stack panel gombjai (Add fill layer stb.) valószínűleg QML-ek (#5), tehát **nem** jönnek QAction-ként, de a hatásukat a diff látja – ez így jó.

## 4. Brush / tool váltás

- **Preset-váltásra nincs hivatalos jel**: a `substance_painter` 17 modulja között nincs tool/brush modul, az eseménylistában nincs tool-esemény, a changelogban 0.2.0–0.3.7 között sincs ilyen (#3 kutatás, [module index](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/module-index), [event](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/event)).
- **Nem hivatalos, gyenge jelek** (mérendő):
  - A Properties dock címe a tool szerint változik (a QAction-szkennelés „Properties - Paint” nevű actiont talált, [vg_painter_actions.py](https://github.com/cgvinny/vg_painter_utilities/blob/main/modules/vg_pt_utils/vg_painter_actions.py)). Ha a `QDockWidget.windowTitleChanged` tool-váltáskor tüzel, a **tool** (Paint/Eraser/Projection…) rögzíthető – a **preset** nem.
  - Tool-shortcutok, ha QAction-ök: a `triggered` megmutatja.
  - Az Assets/Brushes panel QML, a preset-kattintás onnan nem látszik.
- **Tartalék (javasolt v1):** a Brush Step-et a Recording utáni szerkesztőben **kézzel** adja hozzá a felhasználó a lista végére (a #7 döntés szerint a Brush Step úgyis csak a Workflow végén állhat). Ha a mérés szerint a tool-váltás látszik, a szerkesztő felajánlhat egy „Brush Step hozzáadása?” javaslatot.

## 5. Mi zavarja a diffet

| Zavaró tényező | Hatás | Kezelés |
|---|---|---|
| Festés | Szerkezet nem változik; de lehet, hogy minden stroke (vagy thumbnail-frissítés) `LayerStacksModelDataChanged`-et vált ki → sok snapshot. A `TextureStateEvent` festéskor biztosan jön (≥ 500 ms throttling, event doc), de az nem kell. | Debounce + olcsó snapshot (csak szerkezet + blend/opacity). Üres diff = nincs Step. Gyakoriság mérendő. |
| Csúszkahúzás (opacity) | Sok köztes érték; lehet, hogy a Painter maga is csak elengedéskor commitol. | Azonos node + tulajdonság egymást követő változásai egy Step-be (utolsó érték). |
| Undo / Redo a Recording alatt | A diff fordított változást lát (node eltűnik, maszk megszűnik), ami nem katalógus-Step. | (a) Undo QAction `triggered` figyelése → az utolsó Step törlése; (b) ha nincs ilyen action: ha a diff pontosan az utolsó Step fordítottja, töröljük azt. Redo → újra-diff. Uid-stabilitás undo után mérendő. |
| Texture set váltás | Másik stack lesz aktív → teljesen más snapshot. | Snapshot stackenként kulcsolva (texture set + stack név); váltáskor csak új alap-snapshot, nincs Step. v1-ben elég jelezni („a Recording texture set-váltást talált”). |
| Projektváltás / bezárás | Snapshot érvénytelen, uid-ok elavulnak (`ValueError`). | `ProjectAboutToClose` / `ProjectEditionLeft` → Recording leáll, az addigi Step-ek megmaradnak. |
| A Painter „busy” (betöltés, bake, export) | Eseményvihar, olvasás közben kivétel. | `project.is_in_edition_state()` ellenőrzés; minden getter `try`-ban. |
| Plugin saját módosítása | Saját Workflow-futás is eseményt vált ki. | Recording alatt a Workflow-futtatás tiltott, vagy flaggel kiszűrve. |
| Kijelölés-változás | Nem Step, de a current layer követéséhez kell. | Snapshotba `get_selected_nodes` is; ha az esemény nem jön kijelölésre, a polling pótolja. |

## Alternatív csatorna: a History dock modelljének olvasása (nem hivatalos)

Ha a History ablak QWidget-alapú (`QAbstractItemView` + modell), a sorai Qt-n keresztül olvashatók lennének – ez a diffnél pontosabb „mi történt” forrás. Ha QML, akkor nem. **Nincs rá forrás**, és verziónként változhat (12.1.0-ban a History-bejegyzések szövege is változott). A mérőszkript ezt is megnézi; v1-ben legfeljebb kiegészítő jel lehet.

## Bizonytalan, mérendő pontok

1. Tüzel-e a `LayerStacksModelDataChanged`: kijelölés-kattintásra, festés közben (stroke-onként?), opacity-csúszka húzása közben vagy csak elengedéskor, átnevezéskor, undo/redo-ra, texture set váltásra? Hányszor egy műveletre?
2. Létezik-e az esemény 11.1.0-n (`hasattr`).
3. A UI-ból beszúrt generator/filter: előbb üres (`get_source() is None`), és külön eseményben kap source-t?
4. Smart material drag után a csoport neve = a smart material `gui_name()`-je? Smart mask drag után mi jelenik meg (maszk + effektek? folder?)
5. Undo után a visszaállt node uid-ja ugyanaz-e.
6. Van-e Undo/Redo QAction (Ctrl+Z / Ctrl+Y) és tüzel-e rá a `triggered` shortcut-használatkor.
7. Változik-e a Properties dock címe tool-váltáskor; vannak-e tool-QAction-ök.
8. A History dock QWidget-e (olvasható modell) vagy QML.

## Mérőszkript (a Painter Python konzoljába másolandó, mindkét gépen)

Használat: másold be, futtasd. Utána csináld sorban: kattints egy másik layerre; adj hozzá Fill layert; Paint layert; Foldert; fekete maszkot; generatort (válassz egyet); filtert; Levels-t; Anchor pointot; húzd az opacity csúszkát; állíts blend mode-ot; húzz be egy smart materialt és egy smart maskot; fess pár vonást; Ctrl+Z, Ctrl+Y; válts toolt (Paint/Eraser/Projection) és brush presetet; válts texture setet; futtass egy menüparancsot (pl. File > Save). Végül a konzolba: `SPX_REC.stop()`. A konzol kimenetét (vagy a `SPX_REC.dump_path` fájlt) küldd vissza.

```python
# SPExtension - Recording measurement (#17). Paste into Painter's Python console.
import sys, time, json, os, tempfile
from functools import partial
import substance_painter as sp
from PySide6 import QtCore, QtGui, QtWidgets

LS = sp.layerstack


def _safe(f, default=None):
    try:
        return f()
    except Exception as e:  # noqa
        return default if default is not None else "ERR:%s" % type(e).__name__


def _node_rec(n, parent_uid, idx, in_mask, channels):
    t = n.get_type()
    r = {"uid": n.uid(), "type": t.name, "name": _safe(n.get_name), "parent": parent_uid,
         "idx": idx, "mask_stack": in_mask, "visible": _safe(n.is_visible)}
    if _safe(n.has_blending, False) is True:
        if in_mask:
            r["blend"] = _safe(lambda: n.get_blending_mode().name)
            r["opacity"] = _safe(lambda: round(n.get_opacity(), 4))
        else:
            r["blend"] = {c.name: _safe(lambda c=c: n.get_blending_mode(c).name) for c in channels}
            r["opacity"] = {c.name: _safe(lambda c=c: round(n.get_opacity(c), 4)) for c in channels}
    if t in (LS.NodeType.GeneratorEffect, LS.NodeType.FilterEffect):
        src = _safe(n.get_source)
        r["source"] = None if src is None else _safe(lambda: src.resource_id.url())
    return r


def snapshot():
    if not sp.project.is_open() or not sp.project.is_in_edition_state():
        return None
    stack = sp.textureset.get_active_stack()
    channels = list(stack.all_channels().keys())
    nodes = {}

    def walk_layers(layers, parent_uid):
        for i, n in enumerate(layers):
            r = _node_rec(n, parent_uid, i, False, channels)
            r["has_mask"] = _safe(n.has_mask)
            if r["has_mask"] is True:
                r["mask_bg"] = _safe(lambda: n.get_mask_background().name)
            nodes[r["uid"]] = r
            for j, e in enumerate(_safe(n.content_effects, []) or []):
                nodes[e.uid()] = _node_rec(e, n.uid(), j, False, channels)
            for j, e in enumerate(_safe(n.mask_effects, []) or []):
                nodes[e.uid()] = _node_rec(e, n.uid(), j, True, channels)
            if n.get_type() == LS.NodeType.GroupLayer:
                walk_layers(n.sub_layers(), n.uid())

    walk_layers(LS.get_root_layer_nodes(stack), None)
    sel = [n.uid() for n in _safe(lambda: LS.get_selected_nodes(stack), [])]
    key = "%s/%s" % (_safe(lambda: stack.material().name()), _safe(stack.name))
    return {"stack": key, "nodes": nodes, "selection": sel}


def diff(a, b):
    if a is None or b is None:
        return ["(no snapshot: %s -> %s)" % (a is None, b is None)]
    out = []
    if a["stack"] != b["stack"]:
        return ["ACTIVE STACK CHANGED %s -> %s" % (a["stack"], b["stack"])]
    an, bn = a["nodes"], b["nodes"]
    for u in bn.keys() - an.keys():
        out.append("ADDED %s" % json.dumps(bn[u]))
    for u in an.keys() - bn.keys():
        out.append("REMOVED uid=%s %s %s" % (u, an[u]["type"], an[u]["name"]))
    for u in an.keys() & bn.keys():
        for k in set(an[u]) | set(bn[u]):
            if an[u].get(k) != bn[u].get(k):
                out.append("CHANGED uid=%s %s.%s: %s -> %s" % (u, bn[u]["name"], k, an[u].get(k), bn[u].get(k)))
    if a["selection"] != b["selection"]:
        out.append("SELECTION %s -> %s" % (a["selection"], b["selection"]))
    return out


class Recorder(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.t0 = time.perf_counter()
        self.log_lines = []
        self.n_events = 0
        self.last = snapshot()
        self.conns = []
        self.dump_path = os.path.join(tempfile.gettempdir(), "spx_recording_probe.txt")
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._process)
        self.poll = QtCore.QTimer(self)
        self.poll.setInterval(1000)
        self.poll.timeout.connect(lambda: self._process(source="poll"))
        self._env()
        self._connect()
        self.poll.start()
        self.log("RECORDING STARTED - do the actions, then SPX_REC.stop()")

    def log(self, msg):
        line = "[%7.3f] %s" % (time.perf_counter() - self.t0, msg)
        self.log_lines.append(line)
        print(line)

    def _env(self):
        self.log("Painter %s | Python %s | Qt %s | PySide %s" % (
            _safe(sp.application.version_info), sys.version.split()[0],
            QtCore.qVersion(), _safe(lambda: __import__("PySide6").__version__)))
        for name in ("LayerStacksModelDataChanged", "TextureStateEvent", "ProjectEditionLeft"):
            self.log("hasattr(event, %s) = %s" % (name, hasattr(sp.event, name)))

    def _connect(self):
        ev = sp.event
        for cls in ("LayerStacksModelDataChanged", "TextureStateEvent", "ProjectEditionEntered",
                    "ProjectEditionLeft", "ProjectAboutToClose", "BusyStatusChanged"):
            if hasattr(ev, cls):
                cb = partial(self._on_event, cls)
                ev.DISPATCHER.connect_strong(getattr(ev, cls), cb)
                self.conns.append(("ev", getattr(ev, cls), cb))
        mw = sp.ui.get_main_window()
        acts = mw.findChildren(QtGui.QAction)
        self.log("QActions found: %d" % len(acts))
        for a in acts:
            sc = a.shortcut().toString()
            if sc in ("Ctrl+Z", "Ctrl+Y", "Ctrl+Shift+Z"):
                self.log("UNDO/REDO-like action: text=%r objectName=%r sc=%s" % (a.text(), a.objectName(), sc))
            slot = partial(self._on_action, a)
            a.triggered.connect(slot)
            self.conns.append(("act", a, slot))
        for d in mw.findChildren(QtWidgets.QDockWidget):
            self.log("dock: objectName=%r title=%r" % (d.objectName(), d.windowTitle()))
            slot = partial(self._on_dock_title, d)
            d.windowTitleChanged.connect(slot)
            self.conns.append(("dock", d, slot))
            if "history" in (d.windowTitle() + d.objectName()).lower():
                self._probe_history(d)

    def _probe_history(self, dock):
        views = dock.findChildren(QtWidgets.QAbstractItemView)
        quick = [type(w).__name__ for w in dock.findChildren(QtWidgets.QWidget) if "Quick" in type(w).__name__]
        self.log("HISTORY dock: item views=%d quick widgets=%s" % (len(views), quick))
        for v in views:
            m = v.model()
            if m is None:
                continue
            rows = [m.data(m.index(r, 0)) for r in range(min(m.rowCount(), 30))]
            self.log("HISTORY view %s rows=%d first=%s" % (type(v).__name__, m.rowCount(), rows))

    def _on_event(self, cls, e):
        self.n_events += 1
        if cls == "TextureStateEvent":
            self.log("event TextureStateEvent %s" % _safe(lambda: e.action.name))
            return
        self.log("event %s #%d" % (cls, self.n_events))
        if cls in ("ProjectEditionLeft", "ProjectAboutToClose"):
            self.last = None
        self.timer.start()  # debounce

    def _on_action(self, a, checked=False):
        self.log("ACTION triggered text=%r objectName=%r sc=%s checked=%s" % (
            a.text().replace("&", ""), a.objectName(), a.shortcut().toString(), checked))

    def _on_dock_title(self, d, title):
        self.log("DOCK TITLE objectName=%r -> %r" % (d.objectName(), title))

    def _process(self, source="event"):
        cur = _safe(snapshot)
        if isinstance(cur, str):
            self.log("snapshot failed: %s" % cur)
            return
        d = diff(self.last, cur) if (self.last or cur) else []
        if d:
            self.log("DIFF (%s):" % source)
            for line in d:
                self.log("    " + line)
        self.last = cur

    def stop(self):
        self.poll.stop()
        self.timer.stop()
        for kind, obj, slot in self.conns:
            try:
                if kind == "ev":
                    sp.event.DISPATCHER.disconnect(obj, slot)
                elif kind == "act":
                    obj.triggered.disconnect(slot)
                else:
                    obj.windowTitleChanged.disconnect(slot)
            except Exception:
                pass
        self.log("STOPPED. events=%d" % self.n_events)
        with open(self.dump_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.log_lines))
        print("Log written to", self.dump_path)


try:
    SPX_REC.stop()  # noqa: F821  (re-run safe)
except Exception:
    pass
SPX_REC = Recorder()
```

A kimenetből olvasandó: az `event LayerStacksModelDataChanged` sorok száma és időzítése műveletenként (1. pont); a `DIFF (poll)` sorok, amelyek eseményt **nem** kaptak (kihagyott esemény); a generator `source` None → URL átmenete; a smart material csoport neve; undo utáni uid-ok; `ACTION triggered` Undo/menüparancs esetén; `DOCK TITLE` tool-váltáskor; `HISTORY view` sorok.

## Javaslat a spec számára

- Recording = **„snapshot + diff, eseményre ébresztve”**: `LayerStacksModelDataChanged` → 150 ms debounce → snapshot (aktív stack, szerkezet + maszk + blend/opacity + generator/filter source + kijelölés) → diff → katalógus-Step-ek vagy „kimaradt” jelzés. Lassú polling biztonsági hálónak, ha a mérés indokolja.
- Menüparancs: QAction `triggered` + replay-flag; csak a Menu buttonnál is választható actionök rögzülnek.
- Undo a Recording alatt: Undo QAction figyelése (ha van), különben „pontos fordított diff” felismerése.
- Smart material: név szerinti keresés, bizonytalanság esetén a felhasználó választ. Smart mask: mindig a felhasználó választja ki a Recording végén.
- Brush: v1-ben kézzel hozzáadott Brush Step a lista végén (tool-jel legfeljebb javaslat).
- Recording leáll projektzáráskor; texture set váltásnál új alap-snapshot.
- A kód 11.1.0-n és 12.2.0-n azonos (a használt API mind 0.3.0 vagy korábbi).

## Források

Elsődleges (Adobe, Qt):
- [Python API – event modul](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/event)
- [Python API – Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog)
- [Python API – Layerstack navigation](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/navigation)
- [Python API – Generator](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/generator)
- [Python API – SourceSubstance](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/source-module/substance)
- [Python API – Smart material](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/smartmaterial)
- [Python API – Smart mask](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/smartmask)
- [Python API – module index](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/module-index)
- [Painter release notes – All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes)
- [AdobeDocs példa: save_selection](https://github.com/AdobeDocs/painter-python-api/blob/main/src/pages/guides/examples/save_selection.md), [blending_mode](https://github.com/AdobeDocs/painter-python-api/blob/main/src/pages/guides/examples/blending_mode.md)
- [Qt 6 – QAction](https://doc.qt.io/qt-6/qaction.html)

Támogató (harmadik fél, alacsonyabb bizalom):
- [LumaPictures cg-stubs – event.pyi](https://github.com/LumaPictures/cg-stubs/blob/master/substance_painter/stubs/substance_painter-stubs/event.pyi) (payload nélküli esemény)
- [cgvinny/vg_painter_utilities – vg_channel_overlay.py](https://github.com/cgvinny/vg_painter_utilities/blob/main/modules/vg_pt_utils/vg_channel_overlay.py) („may not fire on a bare selection click”), [vg_painter_actions.py](https://github.com/cgvinny/vg_painter_utilities/blob/main/modules/vg_pt_utils/vg_painter_actions.py) (QAction-szkennelés)
