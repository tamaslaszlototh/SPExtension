# SPX Brush Probe – lépések

Ezt **mindkét gépeden** végezd el: az otthonin (11.1.0) és a céges gépen (12.2.0) is. A riportfájlok nevében benne van a Painter verziója, így a két gép eredményei nem keverednek.

**Cél:** kideríteni, hogy a leendő plugin **Brush buttonja** hogyan tud egy kattintással brusht váltani, és honnan veheti a brush képét (thumbnailjét) ikonnak. A Painter hivatalos Python API-ja ezt nem tudja, ezért három kerülőutat próbálunk ki:

- **A**: a plugin csak kijelöli a brusht az Assets ablakban;
- **B**: a Painter régi JavaScript API-ja;
- **C**: a plugin „rákattint” helyetted.

> **3. kör, második próbálkozás (v3.1).** Az előző futásnál a Painter a régi plugin-fájlt használta tovább, mert a „Reload Plugins Folder” nem tölti újra a plugin minden részét. Ez az én hibám volt, nem a tiéd. Most így telepíts:
> 1. **Lépj ki teljesen a Painterből** (File → Exit).
> 2. Töröld a régi `spx_brush_probe` mappát a pluginmappából és a `%APPDATA%\spx_brush_probe` mappát.
> 3. Másold be az új mappát, és **indítsd el a Paintert**.
> 4. A panel címében ennek kell állnia: **„SPX Brush Probe v3.1”**, alján pedig „(checks v3.1)”. Ha nem ez látszik, szólj, és ne folytasd.
>
> A lépések ugyanazok, mint lent a 3. körnél.

> **3. kör.** Köszönöm a 2. kört! Az ikon kérdése megoldódott. A „kattintás szimulálása” (C) viszont megint nem találta az Assets ablakot. Ez a plugin hibája volt, most javítottam.
> - **Mindkét gépen:** mielőtt telepítesz, töröld a pluginmappából a régi `spx_brush_probe` mappát és a `%APPDATA%\spx_brush_probe` mappát (a régi eredmények már nálam vannak).
> - **Otthoni gép:** csak a **2.**, **3.**, **4.** és **6.** lépés kell (előkészítés, felderítés, A próba, C próba), plusz természetesen az 1. (telepítés) és a 8. (eredmények elküldése). Az 5. és a 7. lépést hagyd ki.
> - **Céges gép:** csináld végig az egészet.
> - **Újdonság:** a 3. lépésben egy brusht be kell húznod a panelre (pár másodperc). Az ellenőrzésnél a plugin megkér, hogy **fess egy rövid vonást** a modellre. Így látszik biztosan, melyik brush aktív. Utána a vonást Ctrl+Z-vel visszavonhatod. A „teendő” ablak közben nyitva maradhat, nem akadályoz a festésben.

**Időigény:** kb. 15–20 perc gépenként. Admin jog nem kell, és a plugin semmit nem telepít a rendszerbe.

**Fontos:**
- **Eldobható projekten** dolgozz, ne a munkaprojekteden. A B és a C próba belső, nem dokumentált dolgokat hív meg.
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

## 4. A próba – kijelölés

1. Kattints a **„2. A: kijelölés az Assets ablakban”** gombra.
2. Válaszolj a felugró kérdésekre. Ennél a próbánál neked kell kézzel rákattintanod a kijelölt brushra: amikor a „teendő” ablak kéri, kattints rá egyszer az Assets ablakban, majd nyomd meg a „Rákattintottam” gombot. Utána fess egy vonást.
3. 📝 Az utolsó kérdés a véleményedet kéri: mennyire lenne zavaró, ha a gomb csak kijelölne, és még egyszer rá kellene kattintanod. Ez **fontos**, írd le pár mondatban.

## 5. B próba – JavaScript

1. A legördülő listában válassz egy **másik**, most nem aktív [TOOL] brusht. 📝 Írd fel a nevét.
2. Kattints a **„3. B: aktiválás JavaScripttel”** gombra.
3. Ha kérdés ugrik fel, válaszolj. Ha nem jön kérdés, az is eredmény: a riportból kiderül, miért.
4. 📝 Váltott-e közben a brush (Properties ablak)? Ha a Painter hibát dobott, vagy furcsán viselkedett, írd fel.

## 6. C próba – kattintás szimulálása

1. Válassz megint egy **másik**, most nem aktív [TOOL] brusht. 📝 Írd fel a nevét.
2. Kattints a **„4. C: kattintás szimulálása”** gombra. **Közben ne mozgasd az egeret, és ne kattints semmire.**
3. A plugin legfeljebb négyféleképpen próbál „kattintani” a brushra. Kétféle módszert próbál, mindkettőt egyszeres és dupla kattintással. A Windows-egeres módszernél az egérmutató egy pillanatra magától odaugrik, aztán visszajön. Ez normális.
4. Minden próba után megkér, hogy fess egy vonást, és megkérdezi, hogy a kiválasztott brush mintáját festette-e. Ha **Igen**, a próba ott véget ér.

## 7. Ikon próbák

1. Maradhat ugyanaz a brush, mint a 6. lépésnél.
2. Kattints az **„5. Ikon próbák”** gombra. Ez is eltarthat kb. 1 percig.
3. Amikor kéri, kattints a **„Riport mappa megnyitása”** gombra, és nézd meg a `T2_…` és `T3_…` kezdetű képeket.
4. Válaszolj a kérdésre: van-e köztük olyan, ami a brush thumbnailje, és jó lenne gomb-ikonnak.

## 8. Eredmények elküldése

1. **„Riport mappa megnyitása”** → a `%APPDATA%\spx_brush_probe` mappa.
2. **Csomagold be az egész mappát** (jobb klikk → **Küldés → Tömörített mappa**), és küldd el. Benne lesz:
   - `brush_<verzió>.txt` (a fő riport, a válaszaiddal),
   - `<verzió>_js_api.json`, `<verzió>_js_doc.zip` (a JavaScript API leírása),
   - `<verzió>_*.png` képek.
3. Mellé a 📝 jegyzeteid: a brushok nevei, a lefagyások, és ami furcsa volt.
4. Céges gépről csak azt küldd el, amit a szabályok engednek. A riportban útvonalak, a Painter felületének szerkezete és a brushok nevei vannak.

## 9. Takarítás

1. A projektet **mentés nélkül** zárd be.
2. **Python** menü → vedd ki a pipát az **spx_brush_probe** elől, és lépj ki a Painterből.
3. Töröld a pluginmappából az `spx_brush_probe` mappát, és (elküldés után) a `%APPDATA%\spx_brush_probe` mappát.

---

## Összefoglaló: mit kell visszaküldeni

| | Otthoni (11.1.0) | Céges (12.2.0) |
|---|---|---|
| `%APPDATA%\spx_brush_probe` mappa zipben | ☐ | ☐ |
| A három kipróbált brush neve (A, B, C) | ☐ | ☐ |
| Vélemény a „csak kijelöl” megoldásról (4. lépés) | ☐ | ☐ |
| Lefagyás / hibaüzenet, ha volt | ☐ | ☐ |
