# Második mérési kör – lépések

Ezt **mindkét gépeden** végezd el: az otthonin (11.1.0) és a céges gépen (12.2.0) is. A riportfájlok nevében benne van a Painter verziója, így a két gép eredményei nem keverednek.

**Négy rövid mérés**, mind meglévő mérőeszközzel:

| | Mit mérünk | Eszköz | Idő |
|---|---|---|---|
| A | Megjelenik-e a gomb neve, ha **tollal** lebegsz fölötte | SPX pen probe | ~10 perc |
| B | Brushváltás egy **Photoshop (`.abr`) brushra**, és megvan-e az ikonja | SPX Brush Probe v3.7 | ~10 perc |
| C | Látja-e a plugin a **layer opacity** húzását | SPX Recording Probe | ~5 perc |
| D | Ki tudja-e nyitni a plugin a **bezárt vagy fül mögötti Assets ablakot** | SPX Assets Probe | ~15 perc |

**Összesen kb. 40 perc gépenként.** Admin jog nem kell, és semmi nem települ a rendszerbe.

**Fontos:**
- **Eldobható projekten** dolgozz, ne a munkaprojekteden.
- Ha valami nem úgy működik, ahogy le van írva, **az is eredmény**: írd fel, és menj tovább.
- Ha a Painter lefagy vagy összeomlik, írd fel, melyik lépésnél történt. Indítsd újra, és folytasd a következővel.
- 📝 = írj fel valamit (a panel jegyzetmezőjébe, ha van, különben egy szövegfájlba).

---

## 0. Telepítés (egyszer, mind a négyet)

1. Lépj ki a Painterből.
2. A pluginmappa: `Dokumentumok\Adobe\Adobe Substance 3D Painter\python\plugins\`. Ha az előző körökből bent van az `spx_brush_probe` vagy az `spx_recording_probe` mappa, **töröld őket**, mert az alábbi friss verziók kellenek.
3. Töltsd le és tedd a pluginmappába:
   - **Pen probe** (egy fájl): https://github.com/tamaslaszlototh/SPExtension/raw/research/pen-hover-tooltip/research/pen_hover_probe/spx_pen_probe.py
   - **Assets probe** (egy fájl): https://github.com/tamaslaszlototh/SPExtension/raw/research/open-assets-window/research/spx_assets_probe.py

     ⚠️ Ha a böngésző szövegként megnyitja: jobb klikk → **Mentés másként**. A fájl neve `.py`-re végződjön, ne `.py.txt`-re.
   - **Brush probe** (zip): https://github.com/tamaslaszlototh/SPExtension/raw/prototype/brush-button/prototypes/spx_brush_probe.zip
   - **Recording probe** (zip): https://github.com/tamaslaszlototh/SPExtension/raw/prototype/recording-probe/prototypes/spx_recording_probe.zip

     A zipeket csomagold ki (jobb klikk → **Összes kibontása**), és a benne lévő mappát másold be. ⚠️ Ne legyen dupla mappa (`spx_brush_probe\spx_brush_probe\...`).
4. A végén a pluginmappában ez a négy elem legyen: `spx_pen_probe.py`, `spx_assets_probe.py`, `spx_brush_probe\`, `spx_recording_probe\`.
5. Indítsd el a Paintert. **File → New**, egy egyszerű mesh, **OK**, várd meg a betöltést.

**Egyszerre mindig csak egy probe legyen bekapcsolva.** A **Python** menüben kapcsolod be (pipa) és ki. Ha egy panel nem látszik, keresd a **Window → Views** menüben.

---

## A. Tollas hover (pen probe)

Ha az adott gépen nincs toll/tábla, ezt hagyd ki, és írd fel. 📝

1. **Python** menü → **spx_pen_probe** bekapcsolása. Megjelenik az „SPX pen probe” panel A, B, C és D gombbal.
2. **Reset**, majd **egérrel** tartsd kb. 3 mp-ig a kurzort sorban az A, B, C és D gomb fölött. 📝 Melyiknél jelent meg buborék (tooltip)?
3. **Reset**, majd ugyanez **lebegő tollal**: a toll ne érjen a táblához. 📝 Melyiknél jelent meg buborék? Kiemelődött-e a gomb?
4. Tollal lebegj egy **Painter-saját** ikon fölött is (pl. a bal oldali eszköztáron). 📝 Ott van buborék?
5. Írd be a megfigyeléseket a mezőbe, és nyomd meg a **Save report** gombot.
6. *Opcionális:* a 3. lépés kikapcsolt Windows Inkkel is (Painter-újraindítás kell), utána **kapcsold vissza**.
7. **Python** menü → **spx_pen_probe** kikapcsolása.

## B. `.abr` brush (Brush probe)

Kell hozzá egy Photoshopból importált (`.abr`) brush a Painterben (pl. „Archive Inker”). Ha nincs ilyen, írd fel, és hagyd ki. 📝

1. **Python** menü → **spx_brush_probe** bekapcsolása. A panel címében **„SPX Brush Probe v3.7”** álljon.
2. Legyen nyitva az **Assets** ablak (rácsos nézetben) és a **Properties** ablak. Válaszd a **Paint** eszközt (1-es billentyű).
3. Kattints a **„0. Presetek betöltése”** gombra.
4. **Ikon:** az Assets ablakból húzd az `.abr` brusht a panel szaggatott mezőjébe. Pár másodperc múlva meg kell jelennie a brush nagy képének. 📝 Megjelent? Az a brush? Éles?
5. **Váltás:** válassz egy **másik** brusht kézzel, hogy most ne az `.abr` legyen aktív. A panel legördülő listájában válaszd az `.abr` brusht (**[BRUSH]** jelölésű). 📝 Írd fel a nevét.
6. Kattints a **„2. C: kattintás szimulálása”** gombra. **Közben ne mozgasd az egeret.** Minden próba után fess egy vonást, és válaszolj: az `.abr` brush mintáját festette?
7. **Python** menü → **spx_brush_probe** kikapcsolása.

## C. Layer opacity (Recording probe)

Az előző körben ennél a lépésnél a **brush** opacity csúszkája mozdult. Most a **layer** opacityje kell.

1. **Python** menü → **spx_recording_probe** bekapcsolása.
2. A panel lépésről lépésre vezet. Csak ez a három lépés kell, a többinél nyomd a **„Kihagyom”** gombot:
   - **S00 Előkészítés**: csináld meg, **✔ Kész**.
   - **S04 Paint layer**: adj hozzá egy Paint layert, **✔ Kész**.
   - **S11 Opacity húzása**: a **Layers** ablakban, a Paint layer **saját sorában** fogd meg az opacity értéket, és húzd kb. 3 másodpercig oda-vissza. Csak utána engedd el. ⚠️ **Ne** a Properties ablakban húzd, mert ott Paint eszköznél a brush opacityje van. 📝 Írd be, hol húztad, majd **✔ Kész**.
3. Menj végig **Kihagyom**-mal a lépéssor végéig, hogy a riport elmentődjön.
4. **Python** menü → **spx_recording_probe** kikapcsolása.

## D. Assets ablak megnyitása (Assets probe)

1. **Python** menü → **spx_assets_probe** bekapcsolása. A panel címe: „SPX Assets Probe v1.0”.
2. Húzz be egy brush presetet (pl. Basic Hard) a probe panelre. Utána válassz kézzel egy **másik** brusht, hogy látszódjon a váltás.
3. Az alábbi négy állapot mindegyikénél:
   1. írd be az állapot kódját (S1–S4) a mezőbe,
   2. állítsd elő az állapotot, és nyomd meg az **M4** gombot,
   3. állítsd vissza ugyanazt az állapotot, és nyomd meg az **M1** gombot.

   Mindkét gomb után írd be: aktív lett-e a brush, és jó helyen van-e az Assets ablak. 📝 Ha a brush nem lett aktív, nyomd meg a **„Windows-egér”** gombot is.
   - **S1** Az Assets nyitva van és látszik (ez az összehasonlítási alap).
   - **S2** Az Assets egy fülcsoportban van, de **másik fül** van elöl.
   - **S3** Az Assets **be van zárva** (X), és ikonként ül a Docks eszköztáron.
   - **S4** Az Assets **lebegő** ablak, majd bezárva.
4. Az **S3** állapotban próbáld ki az **M3** (Painter menüpont) és az **M2** gombot is.
5. Nyomd meg a **Diagnosztika** gombot. **Indítsd újra a Paintert**, és 📝 írd meg, jó-e az ablakok elrendezése.

---

## Visszaküldés

1. Zárd be a projektet **mentés nélkül**, és lépj ki a Painterből.
2. Csomagold be ezt a négy mappát (jobb klikk → **Küldés → Tömörített mappa**). Az Intézőbe beírhatod pl. a `%APPDATA%\spx_assets_probe` útvonalat.
   - `%APPDATA%\SPExtension` (benne a `pen_probe_*.txt`)
   - `%APPDATA%\spx_brush_probe`
   - `%APPDATA%\spx_recording_probe` (benne a `rec_<verzió>.txt`)
   - `%APPDATA%\spx_assets_probe` (benne a `report.txt`)
3. Mellé a 📝 jegyzeteidet és azt, ha volt lefagyás.
4. Céges gépről csak azt küldd el, amit a szabályok engednek. A riportokban útvonalak, a Painter felületének szerkezete és a brushok nevei vannak.
5. **Takarítás:** töröld a pluginmappából a négy probe-ot, és az elküldés után a fenti `%APPDATA%` mappákat.

| | Otthoni (11.1.0) | Céges (12.2.0) |
|---|---|---|
| A – pen probe riport + jegyzet | ☐ | ☐ |
| B – brush probe mappa + jegyzet | ☐ | ☐ |
| C – recording riport | ☐ | ☐ |
| D – assets `report.txt` + elrendezés újraindítás után | ☐ | ☐ |
