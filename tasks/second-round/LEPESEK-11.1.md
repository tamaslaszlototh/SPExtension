# Második mérési kör – ismétlés az otthoni gépen (11.1.0)

Köszönöm az előző kört! A tollas és az opacity mérés rendben lefutott. A brush- és az Assets-mérést viszont a mérőszkript egy hibája miatt meg kell ismételni. Most **csak az otthoni gépen** és **csak egy probe-bal**, kb. 10 percben.

A probe most **magától kérdez** (Igen / Nem gombokkal), így nem kell semmit külön felírni.

**Fontos:**
- **Eldobható projekten** dolgozz.
- **Közben ne legyen bekapcsolva más probe.** A Python menüben csak az `spx_assets_probe` előtt legyen pipa.
- Ha valami nem úgy működik, ahogy le van írva, **az is eredmény**. Ha egy kérdés felugrik, válaszolj rá őszintén.

---

## 1. Telepítés

1. Lépj ki a Painterből.
2. A pluginmappából (`Dokumentumok\Adobe\Adobe Substance 3D Painter\python\plugins\`) **töröld** a régi probe-okat: `spx_assets_probe.py`, `spx_pen_probe.py`, `spx_brush_probe\`, `spx_recording_probe\`.
3. Töröld a régi riportmappát is: írd be az Intéző címsorába, hogy `%APPDATA%\spx_assets_probe`, és töröld a mappa tartalmát.
4. Töltsd le az új probe-ot, és tedd a pluginmappába:
   https://github.com/tamaslaszlototh/SPExtension/raw/task/second-round/tasks/second-round/spx_assets_probe.py
   ⚠️ Ha a böngésző szövegként megnyitja: jobb klikk → **Mentés másként**. A fájl neve `spx_assets_probe.py` legyen, ne `.py.txt`.
5. Indítsd el a Paintert. **File → New**, egy egyszerű mesh, **OK**, várd meg a betöltést.
6. Legyen nyitva az **Assets** ablak (rácsos nézetben) és a **Properties** ablak. Válaszd a **Paint** eszközt (1-es billentyű).
7. **Python** menü → **spx_assets_probe** bekapcsolása. **Várj 5 másodpercet**, amíg a panel megjelenik (közben a probe egy rövid tesztet futtat, ehhez kell a nyitott Assets ablak). A panel címe: **„SPX Assets Probe v1.1”**.

## 2. `.abr` brush (kb. 3 perc)

1. Az Assets ablakból húzd az **„Archive Inker”** brusht (vagy más Photoshop/`.abr` brusht) a panel szaggatott mezőjébe. Megjelenik a képe, és jön egy kérdés róla: válaszolj.
2. Válassz az Assets ablakban kézzel egy **másik** brusht, hogy most ne az Archive Inker legyen aktív.
3. Nyomd meg a **„B: brush aktiválása”** gombot. **Ne mozgasd az egeret**, amíg a kérdések nem jönnek, aztán válaszolj. Ha a probe magától odaugrik az egérrel, az normális.

## 3. Assets ablak (kb. 3 perc, magától megy)

Itt a probe maga rendezi az ablakokat: fül mögé teszi, bezárja, lebegővé teszi az Assets ablakot, minden lépés után megméri, és a végén visszaállítja az elrendezést.

1. Húzz be egy **beépített** brusht (pl. „Basic Hard”) a szaggatott mezőbe, és válaszolj a képes kérdésre.
2. Válassz az Assets ablakban kézzel egy **másik** brusht.
3. Nyomd meg a **„D: automatikus Assets-teszt”** gombot, és **kb. 1 percig ne nyúlj semmihez**. Az ablakok közben ugrálni fognak, ez normális. A panel alján látszik, hol tart.
4. A végén a probe egyszer valóban rákattint a brushra, és kérdéseket tesz fel. Válaszolj.
5. Az utolsó kérdés: visszaállt-e az ablakok elrendezése. Ha nem, rendezd vissza kézzel (vagy **Window → Reset UI**), és írd be a megjegyzés mezőbe, mi maradt rossz helyen.

## 4. Visszaküldés

1. Zárd be a projektet **mentés nélkül**, és lépj ki a Painterből.
2. Csomagold be a `%APPDATA%\spx_assets_probe` mappát (jobb klikk → **Küldés → Tömörített mappa**), és küldd el. Benne van a `report.txt` és a brushok képei.
3. Takarítás: töröld a pluginmappából az `spx_assets_probe.py` fájlt.
