# A Smart material buttonok tesztelése (Shelf+ v1.1.0-alpha.1)

Ebben a verzióban van **Smart material button**. Húzz egy smart materialt az Assets ablakból a Panelre. Ezután egy kattintás a csempén a kijelölt layer fölé teszi a smart materialt, a csempét pedig a Painter Layers ablakára húzva oda kerül, ahová ledobod.

Az F teszt egyben a #47-es issue **próbája** is: elfogadja-e a Painter Layers ablaka a Shelf+ által indított húzást? Az eredménye dönti el, hogy a húzás bent marad-e a funkcióban.

A Shelf+ felülete angol, ezért a gombok és feliratok nevét angolul írjuk, ahogy a képernyőn látod.

Kérlek, a teszteket **mindkét gépen** egyszer futtasd le:

- **Otthon:** Painter 11.1.0
- **Munkahelyen:** Painter 12.2.0, admin jog nélkül

Egy kör kb. 20 perc.

**Később:** a Shelf+ az alpha verzióról nem ajánlja fel a frissítést a végleges v1.1.0-ra (ugyanaz a verziószámuk). Ha a v1.1.0 megjelenik, telepítsd kézzel, az 1. lépés szerint. Az eredményeket a [végén lévő táblázatba](#eredmények) írd.

## 1. A verzió telepítése

1. Zárd be a Paintert.
2. Töltsd le a **ShelfPlus-v1.1.0-alpha.1.zip** fájlt a [v1.1.0-alpha.1 kiadás oldaláról](https://github.com/tamaslaszlototh/ShelfPlus/releases/tag/v1.1.0-alpha.1).
3. Nyisd meg a `Documents\Adobe\Adobe Substance 3D Painter\python\plugins` mappát. Ha van benne már `ShelfPlus` mappa, töröld.
4. Másold be a zipből a `ShelfPlus` mappát ebbe a `plugins` mappába.
5. Indítsd el a Paintert, és nyiss meg egy projektet. Olyan projekt másolatát használd, amelynek nem baj, ha megváltozik.
6. Kattints a Panel jobb felső sarkában a **☰** gombra. Az első sornak ezt kell mutatnia: **Shelf+ v1.1.0**.
   - Ha régebbi verziót mutat, vagy a Painter azt írta, hogy „Shelf+ v1.1.0 failed to start; reverted to …”, itt állj meg.
   - Kattints a **☰ → Copy diagnostics** menüpontra, és küldd el, amit kimásol.

## 2. A tesztek

### A. Smart materialok behúzása a Panelre

1. Nyisd meg az Assets ablakot (**Window → Views → Assets**). Húzz egy beépített smart materialt (például *Rust Iron*) egy Groupra. Két csempe közé dobd, vagy a Group nevére.
   - ✅ Ott jelenik meg egy új csempe, ahová dobtad, a smart material képével.
   - ✅ Ha fölé viszed az egeret, a neve a smart material neve.
2. Ugyanezt csináld meg egy saját mentésű smart materiallal is.
3. Jelölj ki együtt az Assets ablakban egy brusht, egy smart materialt és egy materialt (Ctrl+kattintás), és húzd mind a hármat egy Groupra.
   - ✅ Megjelenik egy Brush button és egy Smart material button, a kijelölés sorrendjében.
   - ✅ A Panel azt írja a materialról, hogy *not a brush, tool preset or smart material*.
4. Húzz egy smart maskot egy Groupra.
   - ✅ Nem jön létre csempe, ugyanezzel az üzenettel.

### B. Kattintás egy Smart material buttonra

1. Jelölj ki egy layert a layer stack közepén. Kattints a Smart material buttonra.
   - ✅ A smart material **közvetlenül** a kijelölt layer fölött jelenik meg, és a mappája lesz kijelölve.
   - ✅ Egyetlen **Ctrl+Z** teljesen eltávolítja. A History egy sort mutat: *Shelf+: Add smart material*.
2. Jelölj ki egy **mappán belüli** layert, és kattints újra.
   - ✅ A smart material abba a mappába kerül, a kijelölt layer fölé.
3. Kattints a Layers ablak üres részére, hogy semmi ne legyen kijelölve (ha a Painter engedi), és kattints újra.
   - ✅ A smart material a layer stack tetejére kerül.
4. Zárd be a projektet (**File → Close**), és kattints a csempére.
   - ✅ A Panel azt írja: *Open a project first.* Más nem történik.

### C. Felvétel közben

1. Nyisd meg újra a projektet. Egy Group sorában kattints a **+ → Recorded Workflow** pontra.
2. Kattints a Smart material buttonra.
3. Húzz egy smart materialt az **Assets ablakból** a Layers ablakra.
4. Húzd a Smart material button **csempéjét** a Panelről a Layers ablakra (hagyd ki, ha az F teszt nem sikerül).
5. Kattints a **Stop** gombra.
   - ✅ A szerkesztő három **Add smart material** Step-et mutat (kettőt, ha a 4. lépést kihagytad). Mindkettőnek ki van választva a smart materialja, egyiken sincs *⚠ choose resource*.
6. Zárd be a szerkesztőt mentés nélkül.

### D. Újraindítás után

1. Indítsd újra a Paintert. Figyeld a Panelt, amíg a Painter elindul.
   - ✅ Egyik Smart material buttonon sem jelenik meg a sárga figyelmeztető háromszög, egy pillanatra sem.
2. Nyiss meg egy projektet, és kattints egyszer minden Smart material buttonra.
   - ✅ Mind működik, ugyanúgy, mint a B tesztben.

### E. Hiányzó smart material

1. Zárd be a Paintert.
2. Nyisd meg Jegyzettömbbel a `%APPDATA%\ShelfPlus\layout.json` fájlt. Keress egy Smart material buttont: van benne `"kind": "smart_material"` és egy `"resource"` sor.
3. Írd a név végére, az idézőjelen belülre, hogy `XYZ`, például `"resource://starter_assets/Rust Iron XYZ",`. Mentsd el a fájlt.
4. Indítsd el a Paintert, és nyiss meg egy projektet.
   - ✅ Miután a Painter betöltötte a resource-okat (legfeljebb fél perc), a csempén sárga figyelmeztető háromszög van. Ha fölé viszed az egeret: *(not available on this machine)*.
   - ✅ Kattintásra csak ez az üzenet jelenik meg: *This smart material is not available on this machine: …*. A layer stack nem változik.
   - ✅ Ha a Layers ablakra húzod, ott nem történik semmi. A Panelen belül továbbra is mozgatható.
5. Takarításként húzd a csempét a **Delete** gombra.

### F. Húzás a Layers ablakra (a próba)

1. Húzz ki egy Smart material buttont a Panelről a Painter **Layers** ablakára, és tartsd a stack fölött elengedés nélkül.
   - ✅ A Painter megmutatja a saját ledobási vonalát, mint amikor az Assets ablakból húzol.
2. Engedd el két layer között.
   - ✅ A smart material pontosan oda kerül, ahol a vonal volt.
   - ✅ A csempe a Panelen maradt, a régi helyén.
3. Ismételd meg úgy, hogy egy mappára **rá** engeded, illetve a stack legtetejére és legaljára.
4. Húzd a csempét a Panelen belül egy másik helyre, majd a **Delete** gombra.
   - ✅ Ugyanúgy mozog és törlődik, mint eddig. Nem jön létre új csempe.

Ha az 1. vagy 2. lépés nem sikerül, írd le **pontosan**, mit láttál: nem volt ledobási vonal, „tiltó” kurzor jelent meg, a ledobás nem csinált semmit, vagy valami más került a stackbe. Utána kattints a **☰ → Copy diagnostics** pontra, és küldd el azt is.

## Eredmények

Írd be: **Pass**, vagy **Fail** egy rövid megjegyzéssel, hogy mi történt.

| Teszt | Otthon (11.1.0) | Munkahely (12.2.0) | Megjegyzés |
|---|---|---|---|
| 1. Telepítés: a ☰ v1.1.0-t mutat | | | |
| A. Smart materialok behúzása | | | |
| B. Kattintás | | | |
| C. Felvétel közben | | | |
| D. Újraindítás után | | | |
| E. Hiányzó smart material | | | |
| F. Húzás a Layers ablakra | | | |

**Ha valami nem sikerül:** azonnal, a Painter újraindítása előtt kattints a **☰ → Copy diagnostics** pontra, és másold be az üzenetedbe, amit kimásol.

A kitöltött táblázatot kommentként küldd vissza a [#47-es issue](https://github.com/tamaslaszlototh/ShelfPlus/issues/47) alá.
