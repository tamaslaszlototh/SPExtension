# SPX Brush Probe – lépések

Ezt **mindkét gépeden** végezd el: az otthonin (11.1.0) és a céges gépen (12.2.0) is. A riportfájlok nevében benne van a Painter verziója, így a két gép eredményei nem keverednek.

**Cél:** kideríteni, hogy a leendő plugin **Brush buttonja** hogyan tud egy kattintással brusht váltani, és honnan veheti a brush képét (thumbnailjét) ikonnak. A Painter hivatalos Python API-ja ezt nem tudja, ezért a plugin „rákattint” helyetted a brushra az Assets ablakban (**C próba**). A JavaScriptes utat és a „csak kijelöl” megoldást már kizártuk.

> ## 5. kör (v3.7): az ikon megerősítése, kb. 10 perc gépenként
>
> Köszönöm a céges v3.5-ös kört! Kiderült, hogy a brush nagy (256×256) képe benne van abban a buboréksúgóban, amit a Painter akkor mutat, ha az Assets ablakban a brush fölé viszed az egeret. A v3.7 ezt menti ki. Most azt kell megnézni, hogy ez **mindkét gépen** így van-e.
>
> - **Otthoni gép (11.1.0):** ez itt az első ikonos kör. Csináld végig az alábbi 1–5. lépést.
> - **Céges gép (12.2.0):** elég az 1., 3. és 5. lépés, plusz a 4. lépésből a „4. Ikon sorozat” gomb.
>
> 1. **Telepítés:** lépj ki a Painterből. Töröld a pluginmappából a régi `spx_brush_probe` mappát és a `%APPDATA%\spx_brush_probe` mappát. Töltsd le az új zipet: https://github.com/tamaslaszlototh/SPExtension/raw/prototype/brush-button/prototypes/spx_brush_probe.zip, másold be a mappát, és **indítsd el a Paintert**. A panel címében **„SPX Brush Probe v3.7”** kell, hogy álljon, alján „(checks v3.7)”.
> 2. **Előkészítés:** új projekt, a Paint eszköz kiválasztva, majd a **„0. Presetek betöltése”** gomb. Az Assets ablak legyen nyitva, rácsos (ikonos) nézetben.
> 3. **Behúzás, háromszor:** húzz be egyenként a panel szaggatott mezőjébe
>    - egy beépített brusht (pl. „Basic Hard”),
>    - egy **saját** presetet, ha van,
>    - egy Photoshop (`.abr`) brusht, ha van (pl. „Archive Inker”).
>
>    Minden behúzás után pár másodperc múlva **meg kell jelennie a brush nagy képének** a mezőben. 📝 Mindháromnál írd fel: megjelent? Az a brush volt? Éles?
> 4. Válassz a listából egy brusht, és kattints a **„4. Ikon sorozat (több brush)”** gombra. Ez kb. fél perc. A végén nyisd meg a riport mappát, nézd meg a `T4t_…` (tooltip) képeket, és válaszolj a kérdésekre.
> 5. **Visszaküldés:** a `%APPDATA%\spx_brush_probe` mappa zipben + a 📝 jegyzetek. Utána a 7. lépés szerint takaríts.

**Időigény:** kb. 15–20 perc gépenként. Admin jog nem kell, és a plugin semmit nem telepít a rendszerbe.

**Fontos:**
- **Eldobható projekten** dolgozz, ne a munkaprojekteden. A C próba belső, nem dokumentált dolgokat hív meg.
- Időnként kérdés ugrik fel (Igen / Nem / Nem tudom). Válaszolj őszintén, a válaszaid is a riportba kerülnek. Ha valami nem úgy működik, ahogy le van írva, **az is eredmény**.
- Ha a Painter lefagy vagy összeomlik, írd fel, melyik lépésnél történt. Indítsd újra, és folytasd a következő lépéssel.

---

## 1. Telepítés

1. Töltsd le a zipet: https://github.com/tamaslaszlototh/SPExtension/raw/prototype/brush-button/prototypes/spx_brush_probe.zip
   Csomagold ki (jobb klikk → **Összes kibontása**).
2. A kibontott **`spx_brush_probe`** mappát másold be a pluginmappába (ugyanoda, ahová múltkor az `spx_probe` került):
   `Dokumentumok\Adobe\Adobe Substance 3D Painter\python\plugins\spx_brush_probe\__init__.py`
   ⚠️ Ne legyen dupla mappa (`spx_brush_probe\spx_brush_probe\...`).
3. Indítsd el (vagy indítsd újra) a Paintert. Utána **Python** menü → **spx_brush_probe** (pipa kerül elé). A **Reload Plugins Folder** ehhez nem elég.
4. Megjelenik az **„SPX Brush Probe”** panel. Ha nem látod, keresd a **Window → Views** menüben.

## 2. Előkészítés

1. **File → New**, válassz egy egyszerű meshet, **OK**. Várd meg, amíg betölt.
2. Legyen nyitva az **Assets** ablak (**Window → Views → Assets**) és a **Properties** ablak.
3. Válaszd ki a **Paint** eszközt (ecset ikon a bal oldali eszköztáron, vagy az **1**-es billentyű).
4. Kattints a panelen a **„0. Presetek betöltése”** gombra.
5. A legördülő listában válassz egy **[TOOL]** jelölésű brusht, amelyik **most nem aktív**. Lehetőleg egy egyszerű, beépítettet (pl. „Basic Hard” vagy hasonló). 📝 Írd fel a nevét.
   - Ha a lista üres, vagy nincs benne [TOOL], írd fel, és a 3. lépésnél válassz [BRUSH]-t.

## 3. Felderítés

1. Kattints az **„1. Felderítés”** gombra. A futás kb. 1 perc, közben a Painter nem reagál. Ez normális.
2. Várd meg, amíg a panel alján a „kész” felirat megjelenik.
3. **Behúzás:** fogj meg egy [TOOL] brusht az **Assets** ablakban, és húzd rá a panel szaggatott keretes **„Húzz ide egy brusht”** mezőjére. Engedd el.
   📝 Mi történt? Átalakult a felirat („Behúzva és kiválasztva: …” vagy „Behúzás naplózva”)? Vagy tiltó jel jelent meg az egérmutatón, és nem lehetett elengedni?

## 4. C próba – kattintás szimulálása

1. Válassz egy most nem aktív [TOOL] brusht. 📝 Írd fel a nevét.
2. Kattints a **„2. C: kattintás szimulálása”** gombra. **Közben ne mozgasd az egeret, és ne kattints semmire.**
3. A plugin legfeljebb négyféleképpen próbál „kattintani” a brushra. Kétféle módszert próbál, mindkettőt egyszeres és dupla kattintással. A Windows-egeres módszernél az egérmutató egy pillanatra magától odaugrik, aztán visszajön. Ez normális.
4. Minden próba után megkér, hogy fess egy vonást, és megkérdezi, hogy a kiválasztott brush mintáját festette-e. Ha **Igen**, a próba ott véget ér.

## 5. Ikon próbák

1. Maradhat ugyanaz a brush, mint a 4. lépésnél.
2. Kattints a **„3. Ikon próbák”** gombra. Ez is eltarthat kb. 1 percig.
3. Amikor kéri, kattints a **„Riport mappa megnyitása”** gombra, és nézd meg a `T2_…` és `T3_…` kezdetű képeket.
4. Válaszolj a kérdésre: van-e köztük olyan, ami a brush thumbnailje, és jó lenne gomb-ikonnak.

## 6. Eredmények elküldése

1. **„Riport mappa megnyitása”** → a `%APPDATA%\spx_brush_probe` mappa.
2. **Csomagold be az egész mappát** (jobb klikk → **Küldés → Tömörített mappa**), és küldd el. Benne lesz:
   - `brush_<verzió>.txt` (a fő riport, a válaszaiddal),
   - `<verzió>_js_api.json`, `<verzió>_js_doc.zip` (a JavaScript API leírása),
   - `<verzió>_*.png` képek.
3. Mellé a 📝 jegyzeteid: a brushok nevei, a lefagyások, és ami furcsa volt.
4. Céges gépről csak azt küldd el, amit a szabályok engednek. A riportban útvonalak, a Painter felületének szerkezete és a brushok nevei vannak.

## 7. Takarítás

1. A projektet **mentés nélkül** zárd be.
2. **Python** menü → vedd ki a pipát az **spx_brush_probe** elől, és lépj ki a Painterből.
3. Töröld a pluginmappából az `spx_brush_probe` mappát, és (elküldés után) a `%APPDATA%\spx_brush_probe` mappát.

---

## Összefoglaló: mit kell visszaküldeni

| | Otthoni (11.1.0) | Céges (12.2.0) |
|---|---|---|
| `%APPDATA%\spx_brush_probe` mappa zipben | ☐ | ☐ |
| A kipróbált brushok neve (C, ikon) | ☐ | ☐ |
| Lefagyás / hibaüzenet, ha volt | ☐ | ☐ |
