# SPX Probe – ellenőrzési lépések

Ezt a listát te végzed el, **külön a két gépeden**: egyszer az otthoni, egyszer a céges gépen. A két gép eredményeit tartsd külön (a riportfájlok nevében benne van a Painter verziója).

Cél: kideríteni, hogyan viselkedik a Substance 3D Painter és a hálózat a két gépen, mielőtt eldöntjük, hogyan települjön és frissüljön a plugin.

- **A rész**: el kell végezni a céges gépeden (12.2.0) és az otthoni gépeden (11.1.0) is.
- **B rész**: csak a céges gépen.
- **C rész**: csak az otthoni gépen.

Időigény: kb. 20–30 perc gépenként. Admin jog nem kell. A teszt nem telepít semmit a rendszerbe, és a végén minden törölhető (lásd **D rész**).

Ha egy lépés nem úgy működik, ahogy le van írva, **az is eredmény**. Írd le, mit láttál (vagy készíts képernyőképet), és menj tovább a következőre.

---

## A rész – mindkét gépen

### A1. A pluginmappa megkeresése

1. Indítsd el a Paintert.
2. A felső menüsorban kattints a **Python** menüre.
3. Ha van benne **Plugins Folder** (vagy hasonló, „mappa megnyitása” jellegű) menüpont, kattints rá. Megnyílik egy Intéző-ablak: ez a pluginmappa. Ugorj az A2-re.
4. Ha nincs ilyen menüpont, nyisd meg kézzel az Intézőben:
   `Dokumentumok\Adobe\Adobe Substance 3D Painter\python\plugins`
   - Ha a Dokumentumok mappád OneDrive-on van (az Intéző bal oldalán „OneDrive – <Cégnév>” alatt), akkor a mappa ott keresendő: `OneDrive - <Cégnév>\Documents\Adobe\...`
   - Ha a `python\plugins` mappa nem létezik, hozd létre (előbb a `python`, benne a `plugins` mappát).
5. 📝 **Jegyezd fel** a pluginmappa teljes útvonalát: kattints az Intéző címsorába, és másold ki.

### A2. A próba-plugin bemásolása

1. Töltsd le a zipet böngészőből: https://github.com/tamaslaszlototh/SPExtension/raw/task/machine-checks/checks/spx_probe.zip
   📝 Ha a letöltés nem sikerül (a böngésző, a vírusirtó vagy a céges proxy blokkolja), jegyezd fel az üzenetet, és kérd el a zipet e-mailben.
   Csomagold ki (jobb klikk → **Összes kibontása**).
2. A kibontott **`spx_probe`** mappát (amelyben az `__init__.py`, a `checks.py` és ez a fájl van) másold be a pluginmappába.
   Helyes eredmény: `...\python\plugins\spx_probe\__init__.py`.
   ⚠️ Ne legyen dupla mappa (`spx_probe\spx_probe\__init__.py`). Ha mégis az lett, a belső mappát másold eggyel feljebb.
3. A Painterben: **Python** menü → **Reload Plugins Folder**. Ha nincs ilyen menüpont, indítsd újra a Paintert.

### A3. A plugin bekapcsolása

1. **Python** menü → kattints az **spx_probe** menüpontra (pipa kerül elé).
2. Megjelenik egy **„SPX Probe”** nevű panel, rajta három gombbal.
   - Ha nem látod, nézd meg a **Window** menüben (esetleg **Window → Views**), ott keresd az „SPX Probe” nevet.
   - Ha a pipa megjelent, de panel sehol, vagy hibaüzenet jött: készíts képernyőképet. Nyisd meg a **Window → Views → Log** panelt is, és fotózd le a piros sorokat.

### A4. Diagnosztika futtatása

1. Kattints a panelen az **„1. Diagnosztika futtatása”** gombra.
2. Várj, a futás kb. 10–30 másodperc. Közben a Painter „lefagyhat”, ez normális.
3. A végén felugrik egy ablak: „Diagnosztika kész”, alatta a riportfájl útvonala. Nyomj **OK**-t.
   - Ha hibaüzenet jön helyette, fotózd le.

### A5. Layer stack teszt (eldobható projekten!)

⚠️ Ehhez **ne a munkaprojektedet** használd. Ez a lépés próbarétegeket hoz létre és töröl.

1. **File → New**. Válassz bármilyen meshet (pl. egy régi, egyszerű `.fbx`/`.obj` fájlt), és kattints az **OK**-ra. Várd meg, amíg betölt.
2. Nyisd meg a History panelt: **Window → Views → History**.
3. Kattints az SPX Probe panelen a **„2. Layer stack teszt”** gombra. Várd meg a „kész” ablakot, majd nyomj **OK**-t.
4. 📝 Nézd meg a **History** panelt, és jegyezd fel:
   - a) Van-e **„SPX probe: kivétel”** nevű bejegyzés? (igen/nem)
   - b) **„SPX probe: külső”** és **„SPX probe: belső”**: két külön bejegyzés lett, vagy csak egy („külső”)?
   - c) Van-e kijelöléssel kapcsolatos bejegyzés (pl. „Select…”, „Selection…”, „SPX probe: kijelölés”)?
   - Legjobb, ha a History panelről **képernyőképet** készítesz.
5. Nyomj egyszer **Ctrl+Z**-t. 📝 Mi tűnt el? (Egy próbaréteg, kettő, vagy csak a kijelölés változott?)
6. A projektet **mentés nélkül** zárd be (**File → Close** → *Don't save*).

### A6. Megmarad-e a plugin és a panel helye újraindítás után

1. Fogd meg az SPX Probe panel fejlécét, és húzd ki a Painter ablakából, hogy **lebegő** ablak legyen.
2. Tedd egy jól megjegyezhető helyre (pl. a képernyő jobb alsó sarkába). Ha van **második monitor**, tedd arra.
3. 📝 Jegyezd fel, hova tetted (melyik monitor, melyik sarok).
4. Lépj ki a Painterből: **File → Exit**. Ne a Feladatkezelővel lőd ki.
5. Indítsd újra a Paintert, és várj, amíg teljesen betölt (kb. 10 mp).
6. 📝 Jegyezd fel:
   - a) Magától megjelent-e az SPX Probe panel? Nézd meg azt is, hogy a **Python** menüben van-e pipa az **spx_probe** előtt.
   - b) Ha megjelent: ugyanott van-e (ugyanazon a monitoron, ugyanabban a sarokban)? Lebegő maradt, vagy bedokkolódott?
7. Ha a panel nem jelent meg, kapcsold be újra (A3), és kattints még egyszer az **„1. Diagnosztika futtatása”** gombra. A naplóba így bekerül az újraindítás eredménye is.

### A7. Eredmények összegyűjtése

1. Kattints a panelen a **„Riport mappa megnyitása”** gombra. Megnyílik a `%APPDATA%\spx_probe` mappa.
2. Benne vannak ezek a fájlok (a nevükben a Painter verziója):
   - `diagnosztika_<verzió>.txt`
   - `layerstack_<verzió>.txt`
   - `spx_probe.log`
3. Ezt a három fájlt, a 📝-vel jelölt jegyzeteidet és a képernyőképeket küldd el. A céges gépről ne küldj semmi olyat, amit a céges szabályok tiltanak. A riport csak útvonalakat, verziókat, proxybeállítást és a Painter menülistáját tartalmazza. Ha a felhasználóneved vagy a céged neve szerepel benne, és ez gond, nyugodtan írd át.

---

## B rész – csak a céges (12.2.0) gépen

### B1. Zip letöltése böngészőből

1. Nyisd meg a megszokott böngésződben: https://github.com/cli/cli/releases/latest
2. Görgess le az **Assets** részhez, és kattints a **`gh_<verzió>_windows_amd64.zip`** fájlra.
3. 📝 Jegyezd fel: letöltődött, vagy a böngésző, a vírusirtó vagy a céges proxy blokkolta? Ha blokkolta, mi volt az üzenet?

### B2. Letöltött program futtatása a saját mappádból

Ez azt méri, hogy a cég engedi-e az internetről letöltött programok futtatását. A plugin ehhez **nem** igényel exe-t, ez csak egy opcionális kényelmi telepítőhöz kell.

1. Csomagold ki a B1-ben letöltött zipet (jobb klikk → **Összes kibontása**).
2. Nyisd meg a kibontott mappában a `bin` mappát.
3. Kattints az Intéző címsorába, írd be: `cmd`, majd nyomj Entert. Megnyílik egy fekete parancsablak ebben a mappában.
4. Írd be: `gh --version`, és nyomj Entert.
5. 📝 Jegyezd fel, mi történt:
   - kiírt egy verziószámot → **fut**;
   - „This program is blocked by group policy” / „A rendszergazda letiltotta” üzenet → **AppLocker tiltja**;
   - kék „A Windows megvédte a számítógépet” ablak → **SmartScreen** (ne kattints a „Futtatás mindenképp”-re, csak jegyezd fel);
   - a `cmd` sem nyílt meg → ezt is írd le.
6. Utána a letöltött zipet és a kibontott mappát törölheted.

---

## C rész – csak az otthoni (11.1.0) gépen

1. Nyisd meg a **Creative Cloud** alkalmazást → **Alkalmazások**. Keresd meg a Substance 3D Paintert.
2. 📝 Jegyezd fel: kínál-e frissítést **11.1.1**-re (vagy újabbra)? Ha a **⋯** menüben van „Más verziók” / „Other versions”, nézd meg, szerepel-e ott a 11.1.1.
3. Döntsd el, és 📝 írd le: frissítesz 11.1.1-re, vagy maradsz 11.1.0-n? (A 11.1.0-ban van egy layer stack hiba, amit a 11.1.1 javított.)

---

## D rész – takarítás (a végén, mindkét gépen)

1. A Painterben: **Python** menü → vedd ki a pipát az **spx_probe** elől.
2. Lépj ki a Painterből.
3. Töröld a pluginmappából az `spx_probe` mappát.
4. Töröld a `%APPDATA%\spx_probe` mappát: Win+R, írd be: `%APPDATA%`, Enter, és ott töröld az `spx_probe` mappát. (Előbb küldd el belőle a fájlokat, lásd A7.)

---

## Összefoglaló: mit kell visszaküldeni

| | Céges gép (12.2.0) | Otthoni gép (11.1.0) |
|---|---|---|
| A1 pluginmappa útvonala | ☐ | ☐ |
| A4–A7 három riportfájl | ☐ | ☐ |
| A5 History-megfigyelések (a–c) + Ctrl+Z eredménye + képernyőkép | ☐ | ☐ |
| A6 újraindítás utáni megfigyelések (a–b) | ☐ | ☐ |
| B1 zip letöltése | ☐ | — |
| B2 `gh --version` eredménye | ☐ | — |
| C 11.1.1 frissítés és a döntés | — | ☐ |
