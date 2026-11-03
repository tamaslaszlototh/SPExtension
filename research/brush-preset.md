# Research: brush preset kiválasztása és thumbnailje pluginból

Ticket: [#3](https://github.com/tamaslaszlototh/SPExtension/issues/3) · Map: [#1](https://github.com/tamaslaszlototh/SPExtension/issues/1) · Kutatás dátuma: 2026-11-03

## Kérdés

Be tud-e állítani egy plugin egy adott brush presetet aktív brushnak a Painterben (11.1.0 és 12.2.0)? Hogyan azonosítható stabilan egy preset (resource ID/URL), hogyan kérhető le a thumbnailje, és mi történik, ha a preset nincs meg az adott gépen?

## Röviden

| Kérdés | Válasz | Bizonyosság |
|---|---|---|
| Aktív brush/tool preset beállítása Pythonból | **Nincs rá hivatalos API**, sem 11.1.0-ban, sem 12.2.0-ban. | Ellenőrzött (a modullista és a changelog alapján) |
| Stabil azonosítás | `substance_painter.resource.ResourceID` (`context` + `name` + opcionális `version`), sorosítva `resource://context/name?version=<hash>` URL-ként. | Ellenőrzött |
| Thumbnail lekérése | **Nincs getter.** Csak írni lehet (`set_custom_preview`, `reset_preview`). | Ellenőrzött |
| Hiányzó preset | `Resource.retrieve(id)` üres listát ad, nem dob hibát, így a plugin fel tudja ismerni. Megoldás: a presetet a plugin hozza magával, és a saját shelfjébe importálja. | Ellenőrzött API, a stratégia javaslat |

## Ellenőrzött tények

Az Adobe hivatalos dokumentációja a `helpx.adobe.com/substance-3d-painter-python/...` címről az Experience League-re költözött. A helpx oldalak automatizált lekérésre HTTP 403-at adnak, ezért az alábbi linkek az Experience League változatra mutatnak. A tartalom ugyanaz a Python API referencia.

### 1. A Python API-ban nincs tool/brush modul

- A `substance_painter` csomag 17 modulja: application, async_utils, baking, colormanagement, display, event, exception, export, js, layerstack, logging, project, properties, resource, source, textureset, ui. Egyik sem kezeli az aktív toolt vagy brusht. Forrás: [substance_painter package (module index)](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/module-index)
- A `resource` modulban nincs „aktiváló” függvény. A brush/tool csak enum értékként jelenik meg: `Type.BRUSH`, `Type.PRESET`, `Usage.BRUSH`, `Usage.TOOL`. Forrás: [resource module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/resource)
- A `ui` modulban (`get_main_window`, `add_dock_widget`, `add_toolbar`, `add_action`, `switch_to_mode` stb.) sincs toolválasztás. Forrás: [ui module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/ui)
- A Python API changelog egyetlen verzióban (0.2.0–0.3.7) sem említ tool vagy brush API-t. Forrás: [Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog)
- Közösségi megerősítés (nem Adobe-nyilatkozat, alacsonyabb bizalom): egy 2026-05-05-i feature request szerint „there is no public or private API to set the active brush's Base Color”, és egy nem létező `substance_painter.tool` modult javasol. [Adobe Community feature request](https://community.adobe.com/feature-requests-60/i-would-like-to-be-able-to-set-the-brush-color-of-a-paint-layer-using-the-python-api-1560329). Egy 2025-ös kérdés arról, hogyan érhető el az aktív brush a `js.evaluate`-en keresztül (11.0.1), válasz nélkül maradt. [Adobe Community kérdés](https://community.adobe.com/questions-59/how-to-control-brush-settings-alignment-spacing-mode-via-javascript-api-in-substance-painter-629851)

### 2. Verziók: 11.1.0 és 12.2.0

A [Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog) szerint:

| Python API | Painter | Releváns változás |
|---|---|---|
| 0.2.0 | 7.2.0 | `Resource.show_in_ui()` |
| 0.2.2 | 7.3.0 | `show_resources_in_ui()` |
| 0.2.6 / 0.2.7 | 8.1.2 / 8.2.0 | resource type, usages, tags, parent/children |
| 0.3.4 | 11.0.0 | resource listázás/csere, reload eventek |
| **0.3.5** | **11.1.0** | resource API-t érintő változás nincs |
| 0.3.6 | 12.0.2 | resource API-t érintő változás nincs |
| 0.3.7 | 12.1.0 | OpenPBR channel nevek, geometry mask API; resource-ot nem érint |
| ? | **12.2.0** | **A changelogban nincs bejegyzés** (a legutolsó a 0.3.7 / 12.1.0) |

- A 12.2.0 release notes (2026-10-21) nem említ Python/JS API változást. Az egyetlen brush-hoz kapcsolódó tétel: „[Tool] Add support for additive blending with brush strokes”. Források: [Version 12.2](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/version-12-2), [All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes)
- A 12.0.0 környezetet váltott: „Update Python to 3.13”, „Update Qt to 6.8.6”, „[Scripting] Update JavaScript API to version 1.1.20”. A 11.1 és a 12.x között tehát **eltér a Python és a Qt verziója**, a resource API viszont gyakorlatilag azonos. Forrás: [All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes)
- 12.0.3: „[Python] Painter crash on exit with leftover Qt widgets” javítva. Ez a 11.1-es gépen még előfordulhat, ezért a Panel widgetjeit kilépéskor (`close_plugin`) érdemes rendesen törölni (`ui.delete_ui_element`). Forrás: [All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes)

### 3. Stabil azonosítás: `ResourceID`

Forrás: [resource module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/resource)

- `ResourceID(context: str, name: str, version: str | None = None)`
- `ResourceID.url()` a `resource://context/name?version=<hash>` alakot adja. Visszafelé `ResourceID.from_url(url)`, amely csak `resource://` sémát fogad el, és rossz URL esetén `ValueError`-t dob. A létezést **nem** ellenőrzi.
- A `context` a forrás helye: egy shelf neve (pl. `starter_assets`), illetve a project vagy a session (`from_project`, `from_session`).
- `Resource.retrieve(identifier)`: verzióval megadott ID-ra 0 vagy 1 találatot ad. Verzió nélkül több is lehet, a legújabb az első. Ha a resource nincs meg vagy törölték, **üres listát** ad.
- Keresés: `search(query)`, pl. `"s:starterassets u:basematerial n:Metal Brushed"` (a prefixek jelentését a doc csak példán mutatja). Shelfenként: `Shelf.resources(query)`.
- Tool presetre szűrés: a `Resource.usages()` eredményében `Usage.TOOL` szerepel, a `Resource.type()` pedig várhatóan `Type.PRESET`. A doc nem mondja ki, melyik típus jelöli a tool presetet, ezt élesben ellenőrizni kell.

**Következmény a Layout JSON-ra:** a Brush button a resource URL-t tárolja **verzió nélkül** (`resource://<context>/<name>`), mellé a `gui_name()`-et megjelenítési névnek. Így a preset frissítése (új verzió-hash) nem töri el a hivatkozást, a `retrieve` pedig a legújabbat adja.

### 4. Thumbnail

Forrás: [resource module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/resource)

- A `Resource`-on **nincs** `thumbnail()`/`preview()` getter, és semmi nem ad vissza QPixmapot, QImage-et vagy fájlútvonalat.
- Csak írni lehet: `set_custom_preview(preview_image: str)` (JPEG/PNG/XPM fájl) és `reset_preview()`.
- A doc szerint a thumbnailek importáláskor automatikusan generálódnak, a tárolás helye nem dokumentált.

### 5. Hiányzó preset kezelésére használható API-k

Forrás: [resource module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/resource)

- Felismerés: `Resource.retrieve(ResourceID.from_url(url)) == []`.
- Saját shelf a plugin könyvtárából: `Shelves.add(name, path)` csak sessionre szóló shelfet hoz létre. Mivel a plugin a felhasználói Documents mappában van, ehhez **nem kell admin jog**. Ez a 12.2-es, admin jog nélküli gépen fontos.
- Import shelfbe: `Shelf.import_resource(file_path, resource_usage, name=None, group=None, uuid=None)`. Azonos `uuid` esetén felülírja a meglévőt. A `Shelf.can_import_resources()` False-t ad az alkalmazás shelfjére és a read-only útvonalakra.
- `Shelves.user_shelf()` és `Shelves.application_shelf()` is elérhető.

## Workaroundok az aktív brush beállítására (kockázat szerint)

| # | Megoldás | Mit tud | Kockázat |
|---|---|---|---|
| A | **`Resource.show_in_ui()` / `show_resources_in_ui()`** | A presetet kijelöli (highlight) az Assets ablakban, aktiválni a felhasználó kattintása aktivál. | **Alacsony.** Hivatalos API 0.2.0 óta, mindkét verzióban megvan. Hátrány: két kattintás kell, és a doc nem mondja meg, hogy a highlight megnyitja-e vagy fókuszba hozza-e az Assets ablakot. |
| B | **JavaScript API `substance_painter.js.evaluate()`** | Ha a legacy JS API (`alg.*`, 12.0 óta 1.1.20) tartalmaz tool/preset aktiválást, Pythonból hívható. | **Közepes–magas, nem ellenőrzött.** A JS API doksi csak az alkalmazáson belül érhető el (Help > Scripting documentation > JavaScript API), online nem. Nyilvános forrásban nem találtam toolváltó függvényt, a közösségi kérdés válasz nélkül maradt. A modul „legacy embedded JavaScript engine”-ként szerepel. [js module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/js) |
| C | **Qt UI-automatizálás** (`ui.get_main_window()`, a widgetfa bejárása, az Assets nézetben az elem megtalálása és szimulált kattintás vagy drag) | Elvben „egy kattintásos” aktiválás. | **Magas.** Belső, nem dokumentált widget-/QML-struktúrára épít, ami verziónként változhat. A 12.0 Qt-t váltott (6.8.6), így 11.1 és 12.2 között valószínűleg eltér. Törékeny, és nehéz tesztelni. |
| D | **Saját QDrag a Panelről** a resource URL-lel, a Painter célterületére dobva | Nem ismert, hogy a Painter fogad-e ilyen mime-adatot. | **Magas, nem ellenőrzött.** Nincs róla dokumentáció. |

**Javaslat:** v1-ben az **A** legyen a biztos alap (a Brush button kattintásra a presetet kijelöli az Assets ablakban). A **B**-t egy rövid prototype ticketben érdemes megnézni mindkét gépen. A Painter in-app JS API doksijában kell keresni tool/preset kezelést (pl. `alg.resources`, `alg.tools` vagy hasonló névtér), és ha van, `js.evaluate`-tel kipróbálni. A **C** csak akkor jöhet szóba, ha a B nem működik, és akkor is verzió szerint elágazva, hibánál A-ra visszaesve.

## Thumbnail workaroundok

| # | Megoldás | Kockázat |
|---|---|---|
| T1 | A plugin **saját ikont tárol** a Brush buttonhoz (pl. PNG a Layout mellett). Ezt a felhasználó adja meg, vagy a plugin egyszer elkészíti. | Alacsony, de ellentmond a map döntésének („a brush thumbnailje az ikon, nem kézzel választott”). |
| T2 | A thumbnail kiolvasása a preset fájlból (`.sppr`) vagy a Painter thumbnail-cache-éből | **Nem ellenőrzött.** A fájlformátum és a cache helye nem dokumentált, verziónként változhat. |
| T3 | Képernyőkép az Assets ablak megfelelő eleméről (`QWidget.grab`), miután `show_in_ui()` kijelölte | Magas. A belső UI-szerkezettől függ, ugyanaz a probléma, mint a C-nél. |
| T4 | Ha a plugin maga szállítja a presetet (lásd lent), a thumbnail PNG-t **is a pluginnal együtt szállítjuk**, és `set_custom_preview`-val a Painterben is beállítjuk. | Alacsony, de csak a plugin által szállított presetekre működik. |

**Következmény a map döntésére:** a „Brush buttonnál a brush thumbnailje az ikon” döntés **nem valósítható meg hivatalos API-val** tetszőleges presetre. Ezt újra kell tárgyalni: T1 vagy T4, esetleg T2 egy prototípus után.

## Hiányzó preset (pl. a barát gépén)

- Felismerés: a `retrieve` üres listát ad, ezért a Button letiltott vagy hibaállapotú ikont mutathat, hoverre pedig üzenetet („A preset nem található: <gui_name / URL>”).
- Megelőzés (javaslat): a Layout által hivatkozott, nem gyári presetek fájljai (`.sppr` és a függőségeik) a plugin release-ében vagy egy plugin-adatmappában vannak. Induláskor `Shelves.add("spextension", <plugin_dir>/assets)` sessionre regisztrálja őket. Így a `context` mindkét gépen ugyanaz (`spextension`), és az ID stabil marad. Admin jog nem kell hozzá.
- Gyári presetek (`starter_assets`): mindkét gépen megvannak, de a 11.1 és a 12.2 tartalma eltérhet (pl. a 11.1.0 75 új Ribbon tool presetet hozott). Verzió nélküli URL-lel kell hivatkozni rájuk.

## Bizonytalan pontok, élesben ellenőrizendők

1. A 12.2.0-hoz tartozó Python API verziószám (a changelogban nem szerepel). Ellenőrzés: `substance_painter.application.version_info()`, és `help(substance_painter.resource)` mindkét gépen.
2. Megvan-e a `set_custom_preview`, a `reset_preview`, a `Shelf.import_resource(uuid=...)` és a `Shelves.add` már a 0.3.5-ben (11.1.0)? A changelog nem jelöli, mikor kerültek be. Az online doc a legújabb állapotot mutatja.
3. Mi a tool presetek pontos `type()` és `usages()` értéke (`Type.PRESET` + `Usage.TOOL`?).
4. Megnyitja vagy fókuszba hozza-e a `show_in_ui()` az Assets ablakot, ha az zárva van?
5. Van-e a JS API 1.1.20-ban tool/preset aktiváló függvény (csak az in-app doksiban nézhető meg).
6. A `context` értéke a user shelfnél (`your_assets`?) mindkét gépen ugyanaz-e.

## Források

- [Substance 3D Painter Python API – resource module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/resource)
- [Python API – module index](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/module-index)
- [Python API – ui module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/ui)
- [Python API – js module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/js)
- [Python API – Changelog](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/changelog)
- [Painter release notes – Version 12.2](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/version-12-2)
- [Painter release notes – All Changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes)
- (alacsonyabb bizalom) [Adobe Community feature request: active brush color via Python](https://community.adobe.com/feature-requests-60/i-would-like-to-be-able-to-set-the-brush-color-of-a-paint-layer-using-the-python-api-1560329)
- (alacsonyabb bizalom) [Adobe Community: brush settings via JS API](https://community.adobe.com/questions-59/how-to-control-brush-settings-alignment-spacing-mode-via-javascript-api-in-substance-painter-629851)
