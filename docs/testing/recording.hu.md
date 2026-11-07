# A Recording tesztelése (Shelf+ v0.8.1-rc.1)

Ebben a verzióban már **fel lehet venni egy Workflow-t**: te elvégzed a lépéseket a Painterben, a Panel közben figyel, a végén megnyomod a **Stop** gombot, és a szerkesztőben átnézed a Step-eket.

- Egy Group sorában a **+ → Recorded Workflow** elindítja a felvételt. A Panel tetején megjelenik egy piros **● REC** sáv, amely villog és számolja a Step-eket.
- A REC sáv **Stop** gombja megnyitja a szerkesztőt a felvett Step-ekkel. Innen a szokásos módon menthetsz.
- A szerkesztő alján a **● Continue** gomb további Step-eket vesz fel az éppen nyitott Workflow végére.
- A brusht nem lehet felvenni, mert a Painter nem jelzi, ha brusht váltasz. A Stop után a szerkesztőben add hozzá kézzel.

A Shelf+ felülete angol, ezért a gombok és feliratok nevét angolul írjuk, ahogy a képernyőn látod.

Kérlek, a teszteket **mindkét gépen** egyszer futtasd le:

- **Otthon:** Painter 11.1.0
- **Munkahelyen:** Painter 12.2.0, admin jog nélkül

Egy kör kb. 15 perc. Az eredményeket a [végén lévő táblázatba](#eredmények) írd.

## 1. A verzió telepítése

1. Zárd be a Paintert.
2. Töltsd le a **ShelfPlus-v0.8.1-rc.1.zip** fájlt a [v0.8.1-rc.1 kiadás oldaláról](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.8.1-rc.1).
3. Nyisd meg a `Documents\Adobe\Adobe Substance 3D Painter\python\plugins` mappát. Ha van benne már `ShelfPlus` mappa, töröld.
4. Másold be a zipből a `ShelfPlus` mappát ebbe a `plugins` mappába.
5. Indítsd el a Paintert, és nyiss meg egy projektet. Olyan projekt másolatát használd, amelynek nem baj, ha megváltozik.
6. Kattints a Panel jobb felső sarkában a **☰** gombra. Az első sornak ezt kell mutatnia: **Shelf+ v0.8.1**.
   - Ha régebbi verziót mutat, vagy a Painter azt írta, hogy „Shelf+ v0.8.1 failed to start; reverted to …”, itt állj meg.
   - Kattints a **☰ → Copy diagnostics** menüpontra, és küldd el, amit kimásol.

A saját Layoutod megmarad. A teszt néhány új Buttont ad hozzá, ezeket a végén törölheted.

## 2. A tesztek

### A. Fill + black mask + Dirt + opacity felvétele

1. Jelölj ki egy tetszőleges layert. A *General* sorában kattints a **+** gombra, majd a **Recorded Workflow** pontra.
   - ✅ Megjelenik a piros **● REC** sáv, villog, és ez áll benne: *General: 0 Steps*.
2. A Painterben adj hozzá egy **Fill layert**, rá egy **black maskot**, a maszkra egy **generatort**, és generatornak válaszd a **Dirt**-öt.
   - ✅ A REC sáv minden lépés után eggyel többet számol.
3. A Fill layer **opacity**-jét húzd **50%**-ra a layer saját sorában a Layers ablakban.
4. Állítsd a Fill layer blend mode-ját **Multiply**-ra, aztán nyomj egyszer **Ctrl+Z**-t.
5. Kattints a **Stop** gombra.
   - ✅ Megnyílik a szerkesztő **4 Step**-pel: **Fill layer**, **├ Black mask**, **├ Dirt** *generator on mask*, **└ Opacity 50%** *BaseColor*. Blend mode Step **nincs** benne.
   - ✅ Kattints az Opacity sorra: az érték **pontosan 50**, nem 49 vagy 50.2.
6. Kattints a **Save** gombra. Jelölj ki egy másik layert, és kattints **egyszer** az új csempére.
   - ✅ Ugyanazok a layerek jönnek létre, mint amiket felvettél.
   - ✅ Egyetlen **Ctrl+Z** mindezt visszavonja.

### B. Smart mask

1. Indíts egy felvételt (**+ → Recorded Workflow**). Adj hozzá egy Fill layert, és húzz rá egy **smart maskot** az Assets ablakból (Smart masks).
2. Kattints a **Stop** gombra.
   - ✅ Az utolsó Step sorában ez áll: **Smart mask ⚠ choose resource**, és ez a sor ki van jelölve. A **Save** szürke.
3. Húzd ugyanazt a smart maskot az Assets ablakból a szerkesztőre.
   - ✅ A sorban most a smart mask neve áll, eltűnt a ⚠, és a Save már működik.
4. Kattints a **Cancel** gombra.

### C. Egy régebbi layer kijelölése

1. Indíts egy felvételt. Kattints egy olyan layerre, amely már a felvétel előtt is megvolt (ne arra, amelyik az indításkor ki volt jelölve).
2. Adj hozzá egy black maskot, és kattints a **Stop** gombra.
   - ✅ Legelöl egy **“<a layer neve>”** *select layer* Step áll, alatta beljebb húzva a **Black mask**.
   - Ha két layernek ugyanaz a neve, a Panel figyelmeztet: *Several layers are named “…”*. Ez rendben van.
3. Kattints a **Cancel** gombra.

### D. A festés nem kerül bele

1. Jelölj ki egy **Paint layert**, és indíts egy felvételt. Fess rá néhány vonást.
2. Kattints a **Stop** gombra.
   - ✅ **Nincs Step**, a Panel ezt írja: *Nothing was recorded.*
   - ✅ Nem jelenik meg olyan üzenet, hogy valami „cannot be recorded”.
3. Kattints a **Cancel** gombra.

### E. Egy Workflow folytatása

1. Kattints duplán az A tesztben készült csempére, majd a szerkesztő alján a **● Continue** gombra.
   - ✅ A szerkesztő helyén visszajönnek a Groupok, és megjelenik a REC sáv a Workflow nevével.
2. A Painterben adj hozzá egy **Paint layert**, rá egy **white maskot**, és kattints a **Stop** gombra.
   - ✅ A szerkesztőben a régi 4 Step után ott a **Paint layer** és alatta a **White mask** (nem black).
3. Kattints a **+ Add Step → At the end → Save** pontra, mentsd a Workflow-t, és kattints egyszer a csempéjére.
   - ✅ Lefut, és a Painter elmenti a projektet.

### F. Üzenetek

1. Indíts egy felvételt. A Layers ablakban húzz feljebb vagy lejjebb egy layert.
   - ✅ A Panel ezt írja: *Moving layers cannot be recorded, so it was skipped.* Kattints a **Stop**, majd a **Cancel** gombra.
2. Indíts egy felvételt, adj hozzá egy Fill layert, majd zárd be a projektet (**File → Close**).
   - ✅ A REC sáv eltűnik, és megnyílik a szerkesztő azzal, amit addig felvettél (a Fill layerrel).
3. Ha több texture seted van: indíts egy felvételt, válts át egy másik texture setre, és ott adj hozzá egy layert.
   - ✅ A Panel ezt írja: *Changes in another texture set cannot be recorded…*, és a Stop után ez a layer nem szerepel a Step-ek között.

## Eredmények

Írd be: **Pass**, vagy **Fail** egy rövid megjegyzéssel arról, mi történt. A **Notes** oszlopba írj be mindent, ami furcsa volt, akkor is, ha a teszt sikerült: például villogás, lassúság, rossz helyre kerülő layer vagy Painter-figyelmeztetés.

| Teszt | Otthon (11.1.0) | Munkahely (12.2.0) | Notes |
|---|---|---|---|
| 1. Telepítés: a ☰ v0.8.1-t mutat | | | |
| A. 4 Step, az opacity pontosan 50, futtatás | | | |
| B. Smart mask ⚠-tel, a behúzás kitölti | | | |
| C. Megjelenik a select layer Step | | | |
| D. Festésből nincs Step és nincs üzenet | | | |
| E. Continue, white mask, Save a végén, futtatás | | | |
| F. Üzenetek: mozgatás, projekt bezárása, másik texture set | | | |

**Ha valami nem sikerül:**

1. Rögtön kattints a **☰ → Copy diagnostics** pontra, még a Painter újraindítása előtt.
2. Másold be, amit kimásol, az üzenetedbe. Benne vannak a verziók és a napló legutóbbi sorai.

A kitöltött táblázatot küldd vissza, például hozzászólásként a [#31-es issue-hoz](https://github.com/tamaslaszlototh/SPExtension/issues/31).
