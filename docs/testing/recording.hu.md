# A Recording tesztelése (Shelf+ v0.8.4-rc.1)

Ebben a verzióban már **fel lehet venni egy Workflow-t**: te elvégzed a lépéseket a Painterben, a Panel közben figyel, a végén megnyomod a **Stop** gombot, és a szerkesztőben átnézed a Step-eket.

- Egy Group sorában a **+ → Recorded Workflow** elindítja a felvételt. A Panel tetején megjelenik egy piros **● REC** sáv, amely villog és számolja a Step-eket.
- A REC sáv **Stop** gombja megnyitja a szerkesztőt a felvett Step-ekkel. Innen a szokásos módon menthetsz.
- A szerkesztő alján a **● Continue** gomb további Step-eket vesz fel az éppen nyitott Workflow végére.
- Egy új Fill vagy Paint layer bekapcsolt channelei és a Fill layer tartalma (szín, érték, resource, material) is bekerül. Amit egy Paint layerre festesz, az nem.
- Újdonság a v0.8.3 óta: az **anchor point** megtartja a nevét, egy Fill channel forrása lehet egy anchor point, és egy **meglévő** Fill vagy Paint layer channeleinek vagy tartalmának módosításából **Fill content** Step lesz.
- A brusht nem lehet felvenni, mert a Painter nem jelzi, ha brusht váltasz. A Stop után a szerkesztőben add hozzá kézzel.

A Shelf+ felülete angol, ezért a gombok és feliratok nevét angolul írjuk, ahogy a képernyőn látod.

Kérlek, a teszteket **mindkét gépen** egyszer futtasd le:

- **Otthon:** Painter 11.1.0
- **Munkahelyen:** Painter 12.2.0, admin jog nélkül

Egy kör kb. 15 perc. Az eredményeket a [végén lévő táblázatba](#eredmények) írd.

## 1. A verzió telepítése

1. Zárd be a Paintert.
2. Töltsd le a **ShelfPlus-v0.8.4-rc.1.zip** fájlt a [v0.8.4-rc.1 kiadás oldaláról](https://github.com/tamaslaszlototh/ShelfPlus/releases/tag/v0.8.4-rc.1).
3. Nyisd meg a `Documents\Adobe\Adobe Substance 3D Painter\python\plugins` mappát. Ha van benne már `ShelfPlus` mappa, töröld.
4. Másold be a zipből a `ShelfPlus` mappát ebbe a `plugins` mappába.
5. Indítsd el a Paintert, és nyiss meg egy projektet. Olyan projekt másolatát használd, amelynek nem baj, ha megváltozik.
6. Kattints a Panel jobb felső sarkában a **☰** gombra. Az első sornak ezt kell mutatnia: **Shelf+ v0.8.4**.
   - Ha régebbi verziót mutat, vagy a Painter azt írta, hogy „Shelf+ v0.8.4 failed to start; reverted to …”, itt állj meg.
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

### G. Egy új layer channeljei és tartalma

1. Indíts egy felvételt, és adj hozzá egy **Fill layert**.
2. A Fill layer tulajdonságainál kapcsold ki a **Height** és a **Metallic** channelt.
3. A **BaseColor** színét állítsd erős pirosra, a **Roughness** értékét **0.9**-re.
4. Egy harmadik channelre (például **Normal**) húzz rá egy textúrát vagy procedurált (például *Clouds*) az Assets ablakból.
5. Adj hozzá egy **Paint layert** is, és ott csak a **BaseColor** maradjon bekapcsolva.
6. Kattints a **Stop** gombra, és kattints a Fill layer sorára.
   - ✅ A **Channels** alatt a Height és a Metallic nincs bepipálva.
   - ✅ A **Content** **Per channel**: a BaseColor piros, a Roughness 0.9, a harmadik channelen a választott resource.
   - ✅ A Paint layer sorára kattintva csak a BaseColor van bepipálva.
   - Írd fel a Notes oszlopba, ha a piros világosabb vagy sötétebb, mint amit választottál, vagy ha valamelyik érték hiányzik.
7. Mentsd, jelölj ki egy másik layert, és kattints egyszer a csempére.
   - ✅ Az új Fill layer és Paint layer channelei és értékei ugyanazok, mint amiket felvettél.
8. Nem kötelező: egy új felvételben válaszd a Fill layer **Material** módját, és húzz bele egy materialt. ✅ Stop után a Fill layer sorában **Fill layer: <material neve>** áll.

**Fontos:** ennél a tesztnél a végén mindenképp kattints a **☰ → Copy diagnostics** pontra, és küldd el a kimásolt szöveget akkor is, ha minden sikerült. Benne van, hogyan olvasta ki a Shelf+ a színeket a Painterből.

### H. Anchor pointok és egy meglévő layer Fill tartalma

Ha csak az új dolgokat teszteled, a rövidebb, külön leírás itt van: [anchor-points.hu.md](anchor-points.hu.md).

Kell hozzá egy projekt, amelyben van egy **meglévő Fill layer** és egy **meglévő anchor point** (bármelyik layer tartalmában vagy maszkjában; jobb klikk → *Add anchor point*). A projekt másolatát használd.

1. Jelöld ki a meglévő Fill layert. Indíts egy felvételt.
2. A Fill layer tulajdonságainál kattints a **BaseColor**-ra, nyisd meg az **Anchor points** fület, és válaszd ki a meglévő anchor pointot.
3. Kattints a **Stop** gombra.
   - ✅ Megjelenik egy **Start** blokk (vagy egy *select layer* blokk) egy **Fill content** Step-pel. A sorában ez áll: **BaseColor anchor “<név>”**, az anchor point nevével.
   - ✅ A Step-re kattintva a **Content** alatt a BaseColor **Anchor point**, ezzel a névvel.
4. Mentsd. Vond vissza a változtatást a Painterben (vagy nyisd meg újra a másolatot), jelöld ki ugyanazt a Fill layert, és kattints egyszer az új csempére.
   - ✅ A BaseColor újra az anchor pointot használja.
5. Indíts egy új felvételt. Adj egy **anchor pointot** bármelyik layerhez, és nevezd át **Edges**-re. Utána adj hozzá egy **Fill layert**, és a **Height** forrásának válaszd az **Edges**-t (*Anchor points* fül). Kattints a **Stop** gombra.
   - ✅ Az anchor point sorában **Anchor point “Edges”** áll, a Fill layer sorában **anchor “Edges”**.
6. Mentsd, vond vissza a felvétel változtatásait a Painterben, jelölj ki egy layert, és kattints az új csempére. ✅ Működik.
7. Kattints rá másodszor is. ✅ Semmi nem változik, és az üzenet ez: *An anchor point named “Edges” already exists.*

**Fontos:** ennél a tesztnél a végén mindenképp kattints a **☰ → Copy diagnostics** pontra, és küldd el a kimásolt szöveget akkor is, ha minden sikerült. Benne van, hogyan olvasta ki a Shelf+ az anchor pointot a Painterből.

## Eredmények

Írd be: **Pass**, vagy **Fail** egy rövid megjegyzéssel arról, mi történt. A **Notes** oszlopba írj be mindent, ami furcsa volt, akkor is, ha a teszt sikerült: például villogás, lassúság, rossz helyre kerülő layer vagy Painter-figyelmeztetés.

| Teszt | Otthon (11.1.0) | Munkahely (12.2.0) | Notes |
|---|---|---|---|
| 1. Telepítés: a ☰ v0.8.4-t mutat | | | |
| A. 4 Step, az opacity pontosan 50, futtatás | | | |
| B. Smart mask ⚠-tel, a behúzás kitölti | | | |
| C. Megjelenik a select layer Step | | | |
| D. Festésből nincs Step és nincs üzenet | | | |
| E. Continue, white mask, Save a végén, futtatás | | | |
| F. Üzenetek: mozgatás, projekt bezárása, másik texture set | | | |
| G. Új layer channelei és tartalma (szín, érték, resource, material) | | | |
| H. Anchor point forrás egy meglévő Fill layeren; az „Edges” egyszer lefut, másodszor nem indul | | | |

**Ha valami nem sikerül:**

1. Rögtön kattints a **☰ → Copy diagnostics** pontra, még a Painter újraindítása előtt.
2. Másold be, amit kimásol, az üzenetedbe. Benne vannak a verziók és a napló legutóbbi sorai.

A kitöltött táblázatot küldd vissza, például hozzászólásként a [#31-es issue-hoz](https://github.com/tamaslaszlototh/ShelfPlus/issues/31).
