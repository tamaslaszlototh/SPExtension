# Research: Assets ablak megnyitása pluginból (11.1 vs 12.2)

Ticket: [#20](https://github.com/tamaslaszlototh/SPExtension/issues/20) · Map: [#1](https://github.com/tamaslaszlototh/SPExtension/issues/1) · Mérés: [#21](https://github.com/tamaslaszlototh/SPExtension/issues/21)
Dátum: 2026-11-05 · Célverziók: Painter **11.1.0** (Qt 6.5.x) és **12.2.0** (Qt 6.8.7), Windows

## Kérdés

Hogyan tudja a plugin megnyitni és előre hozni az Assets ablakot, ha az zárva van vagy egy másik fül mögött, hogy a Brush button utána szimulált kattintással aktiválhassa a brusht? Elég-e a `show()` + `raise_()`, vagy a Window → Views → Assets QAction kell? Mennyi idő, amíg az `Alg::ResourceListView` kattintható? Elrontja-e a dock-elrendezést?

## Röviden

1. **Hivatalos API az Assets ablak megnyitására nincs.** A `substance_painter.ui` meglévő dockot nem tud megmutatni vagy elrejteni. A `Resource.show_in_ui()` a doksi szerint csak „kiemeli” a resource-ot az Assets ablakban. Hogy egy **zárt** Assets ablakot kinyit-e, azt a doksi nem mondja. Ezt mérni kell, mert ha igen, a megnyitás hivatalos API-val megoldott.
2. **Megtalálás:** `QApplication.allWidgets()` közül a `QDockWidget`, amelynek `objectName() == "NewShelf"` (címe ` Assets `). Ez 11.1.0-n és 12.2.0-n is mérve van ([#13](https://github.com/tamaslaszlototh/SPExtension/issues/13), [#15](https://github.com/tamaslaszlototh/SPExtension/issues/15)). Nyelvfüggetlen. `findChildren` nem használható, mert 11.1-en halott wrappereket ad.
3. **Javasolt megnyitás (Qt-forrásból levezetve, Painterben még nem mérve):**
   - ha `dock.isHidden()` (zárva): `dock.show()`;
   - minden esetben `dock.raise_()`: dokkolt fülcsoportban ez a Qt-ban az Assets fület teszi aktívvá; lebegő docknál előre hozza (plusz `activateWindow()`);
   - utána `resource.show_in_ui()`, majd **várakozás eseményhurokkal** (QTimer-poll, nem `sleep`), amíg az elem kattintható;
   - utána a már eldöntött kattintás (Qt esemény, tartaléknak Windows-egér).
   A `show()`, a `toggleViewAction().trigger()` és a Painter saját menüpontja Qt-szinten ugyanoda vezet, **ha** a menüpont maga a dock `toggleViewAction`-je. Ha a Painter saját actiont használ (a Docks toolbar miatt ez elképzelhető), akkor az lehet a biztosabb út. Ezt a mérőszkript eldönti.
4. **Időzítés:** dokumentum nem ad számot. A Qt a `show()` után a layoutot és a festést az eseményhurokban végzi, így a kattintást aszinkron kell indítani: pollozni kell, amíg (a) a dock látható, (b) a nézet látható, (c) a modellben megvan az elem, (d) a `visualRect` a viewporton belül van és két egymást követő mérésnél nem mozdul. A prototípus eddig fix 1000–1500 ms-ot várt `show_in_ui()` után ([#13](https://github.com/tamaslaszlototh/SPExtension/issues/13) v3.x). Javasolt felső korlát 3–5 s, ennek leteltével hibaüzenet.
5. **Elrendezés:** a Qt `show()` egy bezárt dockot a korábbi helyére teszi vissza (dokkolt vagy lebegő), a `raise_()` pedig csak a fülválasztást változtatja. Az elrendezés tehát elvben nem sérül, csak az Assets fül lesz előtérben, és az Assets nyitva marad. A kockázat a Painter **Docks toolbarja**: egy bezárt dock ott ikonként áll, és ikonról nyitva „popupként” lebeg a gomb mellett. Hogy a nyers `show()` ezt a saját állapotot megzavarja-e, csak mérésből derül ki.

## Igazolt tények (forrással)

### Painter Python API és Painter-dokumentáció

| Tény | Forrás |
|---|---|
| `Resource.show_in_ui()`: „Highlight this resource in the application shelf UI (Assets window).” A `show_resources_in_ui(resources)` ugyanez listára. A doksi nem írja, hogy zárt ablakot megnyit-e. | [resource module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/resource) |
| A `ui` modulban nincs meglévő dock megmutatása/elrejtése. Van `get_layout(mode)` / `set_layout(state)` / `reset_layout(mode)` (UIMode: Edition, Visualisation, Baking), `show_main_window()`, `add_dock_widget()`. | [ui module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/ui) |
| A Window menü „Views” almenüje: „Lists the windows available in the interface (the checkbox indicate if it is currently visible).” | [Window menu](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/interface/main-menu/window-menu) |
| Docks toolbar: „quick access to the dock windows to quickly open and close them. Clicking on one of the buttons in the toolbar will display the Dock next to its button and floating above the rest of the interface, re-clicking on the button will close it. If the dock move away from its button, it becomes a regular floating window … If closed, the button will be available again in the Dock Toolbar.” | [Toolbars](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/interface/toolbars) |
| A `ui` modul API-ja 11.0 és 12.1 között nem változott; a 12.2-höz nincs listázott API-változás. | [menu-actions-icons research](https://github.com/tamaslaszlototh/SPExtension/blob/research/menu-actions-icons/research/menu-actions-icons.md) |

### Mérések a barát gépén (eddigi ticketek)

| Tény | Forrás |
|---|---|
| Az Assets dock objectName-je `NewShelf`, címe ` Assets `. A nézet `Alg::ResourceListView` (QListView), 11.1-en és 12.2-n is, 12.2-n 1 jelölt. | [#13 resolution](https://github.com/tamaslaszlototh/SPExtension/issues/13), [#15](https://github.com/tamaslaszlototh/SPExtension/issues/15) |
| 11.1-en a `findChildren(QDockWidget)` 18 halott wrappert adott, az `allWidgets()` ugyanazt a 18-at élőként. 12.2-n 20/20 élő. | #13 4. kör, #15 |
| Az aktiválás eddig csak **nyitott, látható** Assets ablakkal volt bizonyítva (feltétel a #13 resolutionban). | #13 |
| A `show_in_ui()` kijelöl és odagörget (11.1 és 12.2). A zárt ablak esete nem volt mérve. | #13, #15 |

### Qt (6.8 forrás és dokumentáció; a 6.5-ös ág ebben azonos)

| Tény | Forrás |
|---|---|
| `toggleViewAction()`: „checkable action … so that the user can show or close this dock widget.” A doksi szerint: „The action can not be used to programmatically show or hide the dock widget. Use the visible property for that.” | [QDockWidget](https://doc.qt.io/qt-6/qdockwidget.html) |
| A forrásban a toggleViewAction **`triggered`** jele a `toggleView(bool)`-hoz kötött: `if (b == q->isHidden()) { if (b) q->show(); else q->close(); }`. Tehát a `trigger()` működik (show-t hív), a `setChecked()` nem. Egy már bepipált action `trigger()`-e viszont **bezárja** a dockot. | [qdockwidget.cpp (6.8)](https://github.com/qt/qtbase/blob/6.8/src/widgets/widgets/qdockwidget.cpp) |
| `QDockWidget::event`: `Show` → toggle action checked, `visibilityChanged`; `Hide` → unchecked. `ZOrderChange` (amit a `raise_()` vált ki) → `if (!isFloating() && layout && onTop) layout->raise(this)`. | ugyanott |
| `QMainWindowLayout::raise(QDockWidget*)`: ha a dock fülcsoportban van, `info->setCurrentTab(widget)`, ami a fülsávon `setCurrentIndex`-et hív. A keresés lebegő fülcsoportokra (`QDockWidgetGroupWindow`) is kiterjed. | [qmainwindowlayout.cpp](https://github.com/qt/qtbase/blob/6.8/src/widgets/widgets/qmainwindowlayout.cpp), [qdockarealayout.cpp](https://github.com/qt/qtbase/blob/6.8/src/widgets/widgets/qdockarealayout.cpp) |
| Fülcsoportban a nem aktív fül dockja **nincs elrejtve** (`isHidden()` hamis): üres geometriát kap, `lower()`, és `visibilityChanged(false)`. Ezért a „zárt” és a „fül mögötti” állapot így különíthető el: `isHidden()` igaz → zárt; különben `visibleRegion().isEmpty()` → takarásban. | qdockarealayout.cpp (`apply`, `itemRect`) |
| `QMainWindow::tabifiedDockWidgets(dock)` megadja, kivel van egy fülcsoportban (diagnosztikához). | [QMainWindow](https://doc.qt.io/qt-6/qmainwindow.html) |

## Bizonytalan pontok (a barát gépén mérendő, #21)

1. **Kinyitja-e a `show_in_ui()` a zárt Assets ablakot, és előre hozza-e a fül mögüliről?** Ha igen mindkét verzión, az a legtisztább (hivatalos) út, és a Qt-trükk csak tartalék.
2. **Docks toolbar-állapot:** zárt Assets (ikon a Docks toolbaron), majd `show()`: hova nyílik ki (az utolsó dokkolt helyére, lebegve, vagy popupként), és utána a Docks toolbar ikonja jól viselkedik-e. Ugyanez a Painter menüpontjával (M3).
3. **A Window → Views → Assets menüpont azonos-e a dock `toggleViewAction()`-jével?** A szkript pointer-összehasonlítással kiírja. Ha nem azonos, a Painter saját actionje lehet a helyes nyitási út (a saját bookkeeping miatt).
4. **Időzítés:** ms-ok a dock láthatóságáig, a nézet láthatóságáig, az elem megjelenéséig és a stabil kattintható pozícióig, mindkét verzión, a három állapotban.
5. **Elrendezés:** a megnyitás után és Painter-újraindítás után is jó-e a dock-elrendezés. A felhasználó szemével kell ellenőrizni.
6. **Assets lebegő ablakban, másik monitoron**, valamint egy **modális dialógus** nyitva tartása: ezek szélső esetek, nem kötelezők.

## Mérési protokoll (barát, #21)

Szkript: [`research/spx_assets_probe.py`](https://github.com/tamaslaszlototh/SPExtension/blob/research/open-assets-window/research/spx_assets_probe.py). Egyetlen fájl a `Documents\Adobe\Adobe Substance 3D Painter\python\plugins` alá, utána Painter-újraindítás és a Python menüben bekapcsolás. Riport: `%APPDATA%\spx_assets_probe\report.txt`.

1. Húzz be egy brush presetet (pl. Basic Hard) a probe panelre. Válassz egy **másik** brusht kézzel, hogy látszódjon a váltás.
2. Minden állapotnál írd be a kódot a mezőbe, állítsd elő az állapotot, nyomd meg **először M4-et**, aztán állítsd vissza az állapotot, és nyomd meg **M1-et**. Mindkettő után írj megjegyzést: aktív lett-e a brush, és jó helyen van-e az Assets. Ha a Qt-kattintás nem aktivált, nyomd meg a „Windows-egér” gombot.
   - **S1** Assets nyitva, látható (kontroll).
   - **S2** Assets dokkolva egy fülcsoportban, de **másik fül** van előtérben.
   - **S3** Assets **bezárva** (X), ikonként a Docks toolbaron.
   - **S4** Assets **lebegő** ablakként, majd bezárva.
3. Az S3 állapotban próbáld ki **M3-at** (Painter menüpont) és **M2-t** is.
4. Nyomd meg a **Diagnosztika** gombot, indítsd újra a Paintert, és írd meg, jó-e az elrendezés.
5. Küldd vissza a `report.txt`-t (11.1.0 és 12.2.0).

## Javaslat a spec számára

- **Brush button folyamat:** `find assets dock` → ha zárt, megnyitás (a mérés szerinti módszerrel: `show_in_ui()`, ha az magától nyit; különben `show()` vagy a Painter menüpontja) → `raise_()` → `show_in_ui()` → aszinkron várakozás (poll 15–50 ms, max ~3–5 s) → kattintás (Qt esemény, tartalék Windows-egér) → ellenőrzés. Időtúllépésnél üzenet, a „csak kijelöl” tartalék nincs (a felhasználó döntése).
- Az Assets ablak **nyitva marad** a kattintás után. Visszazárás vagy az előző fül visszaállítása nem kell a v1-be (a döntés is „kinyitja” volt). Ha zavaró, ez később opcióként hozzáadható.
- `toggleViewAction().trigger()` csak `isChecked()` ellenőrzés után, különben bezár.
- Minden hozzáférés `allWidgets()` + `try` + `shiboken6.isValid`, ahogy a #13 tanulsága is mondja.
- Verzió-elágazás várhatóan nem kell. Ha a mérés eltérést mutat (pl. 11.1-en a `show_in_ui()` nem nyit, 12.2-n igen), a közös út az explicit megnyitás, utána `show_in_ui()`, ez mindkettőn jó.
