# A Workflow-szerkesztő tesztelése (Shelf+ v0.7.2-rc.1)

Ebben a verzióban már **saját Workflow-kat lehet összerakni a Panelen**, és a meglévőket is lehet javítani:

- Egy Group sorában a **+ → Workflow button** megnyitja a szerkesztőt egy üres Workflow-val.
- Egy Workflow buttonra **duplán kattintva** a szerkesztőben nyílik meg. Egy kattintásra továbbra is lefut, csak egy pillanattal később: a Shelf+ kivárja, jön-e második kattintás. Jobb klikk → **Edit Workflow…** is megnyitja.
- A szerkesztő a Step-eket aszerint csoportosítja, hogy melyik layeren dolgoznak. A **Start** alatt, legfelül azok a Step-ek állnak, amelyek a Button megnyomásakor kijelölt layeren dolgoznak. A brush, menüparancs és mentés Step-ek az **At the end of the Workflow** alatt vannak.

A Shelf+ felülete angol, ezért a gombok és feliratok nevét angolul írjuk, ahogy a képernyőn látod.

Kérlek, a teszteket **mindkét gépen** egyszer futtasd le:

- **Otthon:** Painter 11.1.0
- **Munkahelyen:** Painter 12.2.0, admin jog nélkül

Egy kör kb. 15 perc. Az eredményeket a [végén lévő táblázatba](#eredmények) írd.

## 1. A verzió telepítése

1. Zárd be a Paintert.
2. Töltsd le a **ShelfPlus-v0.7.2-rc.1.zip** fájlt a [v0.7.2-rc.1 kiadás oldaláról](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.7.2-rc.1).
3. Nyisd meg a `Documents\Adobe\Adobe Substance 3D Painter\python\plugins` mappát. Ha van benne már `ShelfPlus` mappa, töröld.
4. Másold be a zipből a `ShelfPlus` mappát ebbe a `plugins` mappába.
5. Indítsd el a Paintert, és nyiss meg egy projektet. Olyan projekt másolatát használd, amelynek nem baj, ha megváltozik.
6. Kattints a Panel jobb felső sarkában a **☰** gombra. Az első sornak ezt kell mutatnia: **Shelf+ v0.7.2**.
   - Ha régebbi verziót mutat, vagy a Painter azt írta, hogy „Shelf+ v0.7.2 failed to start; reverted to …”, itt állj meg.
   - Kattints a **☰ → Copy diagnostics** menüpontra, és küldd el, amit kimásol.

A saját Layoutod megmarad. A teszt néhány új Buttont ad hozzá, ezeket a végén törölheted.

## 2. A tesztek

### A. „Fill layer + Black mask + Dirt + Opacity 50%” összerakása kézzel

1. A *General* sorában kattints a **+** gombra, majd a **Workflow button** pontra. A Groupok helyén megjelenik a szerkesztő.
   - ✅ A **Save** gomb szürke, fölötte ez áll: *Add a Step first.*
2. Kattints a **+ Add Step → Layer → Fill layer**, majd a **+ Add Step → Mask → Black mask** pontra.
   - ✅ A *Black mask* beljebb húzva, a *Fill layer* alatt áll.
3. Kattints a **+ Add Step → Effect → Generator on the mask** pontra.
   - ✅ A sorban ez áll: **Generator ⚠ choose resource**, és a Save szürke.
4. Amíg ez a sor ki van jelölve, kattints a Step-ek alatti **Resource** mező melletti **Choose…** gombra, és írd be a keresőbe: `dirt`. (Generatort nem lehet kihúzni az Assets ablakból, ezért ebből a listából lehet kiválasztani.)
   - ✅ A lista a Painter azon resource-ait mutatja, amelyek nevében benne van a *dirt*, mindegyik után a típusával.
   - Válaszd a **Dirt generatort**: vidd az egeret a sorok fölé, és azt válaszd, amelyiknek a címe `mg_dirt`-re végződik. Kattints a **Choose** gombra.
   - ✅ A sorban most **Dirt** áll, és eltűnt a ⚠.
   - Írd fel a Notes oszlopba, milyen típust mutatott mellette a lista.
5. Kattints a **+ Add Step → Setting → Opacity** pontra. A Step-ek alatt hagyd bepipálva a **BaseColor** sort, és állítsd **50 %**-ra.
   - ✅ Fent a név: **Fill layer + Black mask + Dirt + Opacity 50%**.
6. Kattints a **Save** gombra.
   - ✅ Visszajönnek a Groupok, és a *General* végén ott egy új csempe. Az ikonja a Fill layer Step ikonja.
7. Jelölj ki egy layert a Layers ablakban, és kattints **egyszer** az új csempére.
   - ✅ A kijelölt layer fölött megjelenik egy Fill layer fekete maszkkal, a maszkban Dirt generatorral, és a BaseColor opacity-je 50%.
   - ✅ Egyetlen **Ctrl+Z** mindezt visszavonja.

### B. Újranyitás, az Opacity áttétele a Start blokkba

1. **Kattints duplán** az A tesztben készült csempére.
   - ✅ Megnyílik a szerkesztő a négy Step-pel. A Layers ablakban nem jelenik meg semmi új: a dupla kattintás nem futtatta le.
2. Az **Opacity** sorában kattints a **↑** gombra annyiszor, hogy legfelülre kerüljön, a **Start: the layer selected when it runs** alá. Áthúzással is odaviheted.
3. Kattints a **Save** gombra. Jelölj ki egy layert, és kattints egyszer a csempére.
   - ✅ A kijelölt layer BaseColor opacity-je lesz 50%, a fölötte létrejött új Fill layeré 100% marad.

### C. A Save nem kerülhet layer Step fölé

1. Nyisd meg a szerkesztőben bármelyik Workflow-t, és ha nincs benne, add hozzá: **+ Add Step → At the end → Save**.
2. Húzd a **Save** sort egy layer sor fölé, és engedd el.
   - ✅ Visszaugrik az *At the end of the Workflow* alá, és a Panel ezt írja: *A Step cannot go there; it was put back.*
3. Húzz egy **Fill layer** sort (félkövér sor) egy másik layer Step-jei közé.
   - ✅ Ez is visszaugrik: layer nem kerülhet egy másik layer belsejébe.
4. Kattints a **Cancel** gombra. Semmi nem mentődik.

### D. Saját ikon egy Workflow-nak

1. Kattints duplán egy Workflow csempére. A szerkesztőben kattints a név bal oldalán lévő ikonra, majd a **Choose image…** pontra, és válassz egy tetszőleges PNG vagy JPG képet a gépedről.
2. Kattints a **Save** gombra.
   - ✅ A csempén a te képed látszik, és a Painter újraindítása után is megmarad.
3. Nem kötelező: nyisd meg újra, kattints az ikonra → **Use the first Step's icon**, és mentsd. A csempe újra a Step ikonját mutatja.

### E. Layer kiválasztása név alapján

1. Csinálj egy új Workflow-t: **+ Add Step → Layer → Select layer by name**.
   - ✅ A sorban ez áll: **⚠ enter a name**, és a Save szürke.
2. Jelölj ki egy layert a Layers ablakban, és kattints a **Use selected layer's name** gombra.
   - ✅ A névmezőben megjelenik a layer neve, és a Save már működik.

### F. Smart mask behúzása az Assets ablakból

1. Csinálj egy új Workflow-t: **+ Add Step → Layer → Fill layer**, majd **+ Add Step → Mask → Smart mask**.
   - ✅ A smart mask sorában ez áll: **Smart mask ⚠ choose resource**.
2. Amíg ez a sor ki van jelölve, húzz rá a szerkesztőre egy tetszőleges **smart maskot** az Assets ablakból (Smart masks).
   - ✅ A sorban most a smart mask neve áll, és eltűnt a ⚠.
   - Ha a húzás el sem indul, vagy nem változik semmi, írd fel, melyik smart maskkal próbáltad.
3. Kattints a **Cancel** gombra.

### G. Egy új layer channeljei és tartalma

1. Csinálj egy új Workflow-t: **+ Add Step → Layer → Fill layer**, és kattints a **Fill layer** sorra.
   - ✅ A Step-ek alatt a **Channels** a texture set channeljeit sorolja fel, mindet bepipálva.
2. Vedd ki a pipát a **Height** elől. A **Content** legyen **Per channel**.
   - ✅ Minden bepipált channel kap egy sort: **Value**, színgombbal (BaseColor) vagy 0 és 1 közötti számmal (Roughness, Metallic…).
3. Kattints a **BaseColor** színgombjára, és válassz egy erős pirosat. A **Roughness** legyen **0.9**.
4. A **Normal** sorában (vagy bármelyik másik channelnél) állítsd a **Value**-t **Resource**-ra, kattints a **Choose…** gombra, keress egy textúrát vagy procedurált (például `clouds`), és válaszd ki.
5. Kattints a **Save** gombra. Jelölj ki egy layert, és kattints egyszer az új csempére.
   - ✅ Az új Fill layer tulajdonságainál a Height ki van kapcsolva, a BaseColor piros, a Roughness 0.9, és a 4. lépés channeljén a választott resource van.
   - Írd fel a Notes oszlopba, ha a piros világosabb vagy sötétebb, mint amit választottál.
6. Nyisd meg újra (dupla kattintás). A Fill layer sorában a **Content** legyen **One material**, kattints a **Choose…** gombra, és válassz egy tetszőleges materialt. Mentsd és futtasd.
   - ✅ A sorban **Fill layer: <material neve>** áll, és az új layeren az a material látszik.
7. Csinálj egy Workflow-t **Paint layer**-rel, a **BaseColor** kivételével vedd ki az összes channel pipáját, mentsd és futtasd.
   - ✅ Az új Paint layeren csak a BaseColor van bekapcsolva. (Paint layernek nincs Content beállítása.)

### H. Workflow törlése a szerkesztőből

1. Nyisd meg a szerkesztőben az egyik általad készített Workflow-t, és kattints a név melletti **kuka** ikonra.
   - ✅ Rákérdez: *Delete "…"?*. A **No** mindent úgy hagy, ahogy volt.
2. Kattints újra a kukára, és válaszolj **Yes**-szel.
   - ✅ A szerkesztő bezárul, a csempe eltűnik, és pár másodpercig megjelenik az **Undo**. Az Undo visszahozza a csempét.

## Eredmények

Írd be: **Pass**, vagy **Fail** egy rövid megjegyzéssel arról, mi történt. A **Notes** oszlopba írj be mindent, ami furcsa volt, akkor is, ha a teszt sikerült: például villogás, lassúság, el nem induló húzás vagy Painter-figyelmeztetés.

| Teszt | Otthon (11.1.0) | Munkahely (12.2.0) | Notes |
|---|---|---|---|
| 1. Telepítés: a ☰ v0.7.2-t mutat | | | |
| A. Fill + Black mask + Dirt + Opacity 50% összerakása (Dirt a listából) és futtatása | | | |
| B. Dupla kattintás újranyit; Opacity a Startba | | | |
| C. A Save és a layer sor visszaugrik | | | |
| D. Saját ikon lemezről | | | |
| E. Layer kiválasztása név alapján | | | |
| F. Smart mask behúzása az Assets ablakból | | | |
| G. Layer channelek; channelenkénti szín, érték és resource; egy material | | | |
| H. A szerkesztőből törlés előtt rákérdez | | | |

**Ha valami nem sikerül:**

1. Rögtön kattints a **☰ → Copy diagnostics** pontra, még a Painter újraindítása előtt.
2. Másold be, amit kimásol, az üzenetedbe. Benne vannak a verziók és a napló legutóbbi sorai.

A kitöltött táblázatot küldd vissza, például hozzászólásként a [#30-as issue-hoz](https://github.com/tamaslaszlototh/SPExtension/issues/30).
