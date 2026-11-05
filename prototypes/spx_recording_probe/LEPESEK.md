# SPX Recording Probe – lépések

Ezt **mindkét gépeden** végezd el: az otthonin (11.1.0) és a céges gépen (12.2.0) is. A riportfájl nevében benne van a Painter verziója, így a két gép eredményei nem keverednek.

**Cél:** a leendő plugin tudni fogja „felvenni”, amit a Painterben csinálsz (Recording): layert adsz hozzá, maszkot teszel rá, generatort választasz, és ebből a Panelen egy gomb (Workflow button) lesz. Ehhez a pluginnak észre kell vennie, mi változott a Layers ablakban. Ez a mérés megmutatja, hogy mit lát ebből a plugin és mikor: minden lépés után mi jelent meg, mi maradt ki, és mit csinál a Ctrl+Z.

**Időigény:** kb. 20–25 perc gépenként. Admin jog nem kell, a plugin semmit nem telepít a rendszerbe, és **semmit nem kattint helyetted**: csak figyel.

**Ha egy körben szeretnéd:** a [második mérési kör](https://github.com/tamaslaszlototh/SPExtension/issues/21) (tollas hover, Assets ablak, `.abr` brush) mérőpluginjai mellette is futhatnak. Előbb ezt csináld végig, utána azokat.

**Fontos:**
- **Eldobható projekten** dolgozz, ne a munkaprojekteden.
- A panel lépésről lépésre vezet. Minden lépésnél: **olvasd el, csináld meg, nyomd a „✔ Kész” gombot.** Ha egy lépés nem megy, vagy nincs hozzá, amire szükség van, nyomd a **„Kihagyom”** gombot, és ha tudod, írd be a jegyzetbe, miért.
- Ahol a lépés 📝 jelet mutat, írj valamit a jegyzet mezőbe, **mielőtt** a „Kész”-re kattintasz.
- Két lépés között ne csinálj mást a Painterben: ami a lépés alatt történik, azt a riport annak a lépésnek tulajdonítja.
- Ha valami nem úgy működik, ahogy le van írva, **az is eredmény**. Írd be a jegyzetbe.
- Ha a Painter lefagy vagy összeomlik, írd fel, melyik lépésnél (pl. S16). Indítsd újra, és küldd el a riportot úgy, ahogy van; nem kell elölről kezdeni.

---

## 1. Telepítés

1. Töltsd le a zipet: https://github.com/tamaslaszlototh/SPExtension/raw/prototype/recording-probe/prototypes/spx_recording_probe.zip
   Csomagold ki (jobb klikk → **Összes kibontása**).
2. A kibontott **`spx_recording_probe`** mappát másold be a pluginmappába (ugyanoda, ahová a korábbi probe-ok kerültek):
   `Dokumentumok\Adobe\Adobe Substance 3D Painter\python\plugins\spx_recording_probe\__init__.py`
   ⚠️ Ne legyen dupla mappa (`spx_recording_probe\spx_recording_probe\...`).
3. Indítsd el (vagy indítsd újra) a Paintert. Utána **Python** menü → **spx_recording_probe** (pipa kerül elé).
4. Megjelenik az **„SPX Recording Probe v1.0”** panel. Ha nem látod, keresd a **Window → Views** menüben. Húzd olyan helyre, ahol a Layers ablak mellett kényelmesen látod.

## 2. Mi kell hozzá

- Egy új, eldobható projekt (a panel első lépése (S00) ezt kéri).
- Nyitva: **Layers**, **Assets**, **History** (Window → Views → History), **Properties**.
- Az Assets ablakban legyen elérhető legalább egy **smart material** és egy **smart mask** (a beépítettek jók, pl. bármelyik a Smart materials / Smart masks szűrő alatt).

## 3. A mérés

Kövesd a panelt S00-tól S30-ig. Néhány lépés, amire külön figyelj:

- **S01 Nyugalom:** tényleg ne nyúlj semmihez 5 másodpercig. Ez méri az „alapzajt”.
- **S11 Opacity húzása:** ne engedd el a csúszkát kb. 3 másodpercig, közben mozgasd. Ez azt méri, hogy a plugin a köztes értékeket is látja-e, vagy csak a végsőt.
- **S14–S15 Smart material / Smart mask:** **előbb** a probe panel szaggatott mezőjébe húzd (a felirat kiírja a nevét), **utána** a Layers ablakba.
- **S16 Festés:** pontosan 3 vonás.
- **S18–S21 Undo/Redo:** mindegyiknél csak azt az egy dolgot csináld, amit a lépés kér.
- **S25 File → Save:** ha mentési ablak jön, mentsd bárhova (pl. Asztal); utána törölheted.

Az utolsó lépés (S30) után a panel azt írja: **„Kész! Köszönöm”**.

## 4. Ha a panel nem indul, vagy hibát ír

Nyisd meg a **Window → Views → Python Console**-t (vagy a Log ablakot), és küldd el képernyőképen, amit ott látsz. A riportfájl ilyenkor is hasznos, ha létrejött.

## 5. Eredmények elküldése

1. **„Riport mappa megnyitása”** → a `%APPDATA%\spx_recording_probe` mappa.
2. Küldd el a **`rec_<verzió>.txt`** fájlt (pl. `rec_11.1.0.txt`, `rec_12.2.0.txt`).
3. Mellé, ha volt: lefagyás, hibaüzenet, vagy ami furcsa volt.
4. Céges gépről csak azt küldd el, amit a szabályok engednek. A riportban a Painter verziója, a felület belső nevei (menük, ablakok), a layerek és a behúzott assetek nevei vannak; a projektedből semmi más nem.

## 6. Takarítás

1. **Python** menü → vedd ki a pipát az **spx_recording_probe** elől, és lépj ki a Painterből.
2. Töröld a pluginmappából az `spx_recording_probe` mappát, (elküldés után) a `%APPDATA%\spx_recording_probe` mappát, és az S25-ben mentett projektet.

---

## Összefoglaló: mit kell visszaküldeni

| | Otthoni (11.1.0) | Céges (12.2.0) |
|---|---|---|
| `rec_<verzió>.txt` | ☐ | ☐ |
| Lefagyás / hibaüzenet, ha volt | ☐ | ☐ |
