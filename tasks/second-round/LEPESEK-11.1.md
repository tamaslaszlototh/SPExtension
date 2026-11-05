# Második mérési kör – ismétlés az otthoni gépen (11.1.0)

Köszönöm az előző kört! A tollas és az opacity mérés rendben lefutott. A brush- és az Assets-mérést viszont a mérőszkript egy hibája miatt meg kell ismételni. Most **csak az otthoni gépen** és **csak egy probe-bal**, kb. 15–20 percben.

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

## 2. `.abr` brush

1. Az Assets ablakból húzd az **„Archive Inker”** brusht (vagy más Photoshop/`.abr` brusht) a panel szaggatott mezőjébe.
2. Megjelenik a brush képe, és jön egy kérdés róla. Válaszolj.
3. Válassz az Assets ablakban kézzel egy **másik** brusht, hogy most ne az Archive Inker legyen aktív.
4. Az **állapot** mezőbe írd be: `B`. Nyomd meg az **„M4 csak show_in_ui()”** gombot.
5. **Ne mozgasd az egeret**, amíg a kérdések nem jönnek. Válaszolj a kérdésekre. Ha a probe azt kéri, fess egy vonást. Ha a probe magától odaugrik az egérrel, az normális.

## 3. Assets ablak megnyitása

1. Húzz be egy **beépített** brusht (pl. „Basic Hard”) a szaggatott mezőbe. Válaszolj a képes kérdésre.
2. Az alábbi négy állapot mindegyikénél kétszer mérsz:
   1. Válassz kézzel egy **másik** brusht. Írd be az állapot kódját az állapot mezőbe. Állítsd elő az állapotot, nyomd meg az **M4** gombot, és válaszolj a kérdésekre.
   2. Válassz megint kézzel egy másik brusht. Állítsd elő **újra** ugyanazt az állapotot, nyomd meg az **M1** gombot, és válaszolj a kérdésekre.

   | Kód | Állapot |
   |---|---|
   | `S1` | Az Assets nyitva van és látszik. |
   | `S2` | Az Assets egy fülcsoportban van, de **másik fül** van elöl (húzd egy másik ablak fülei közé, és kattints a másik fülre). |
   | `S3` | Az Assets **be van zárva** (X a sarkában). |
   | `S4` | Az Assets **lebegő** ablak (húzd ki a fülénél fogva), majd bezárva. |

3. Az **S3** állapotban mérj az **M3** és az **M2** gombbal is (előtte mindig zárd be újra az Assets ablakot, és válassz másik brusht).
4. Nyomd meg a **Diagnosztika** gombot.

## 4. Visszaküldés

1. Zárd be a projektet **mentés nélkül**, és lépj ki a Painterből.
2. Csomagold be a `%APPDATA%\spx_assets_probe` mappát (jobb klikk → **Küldés → Tömörített mappa**), és küldd el. Benne van a `report.txt` és a brushok képei.
3. Takarítás: töröld a pluginmappából az `spx_assets_probe.py` fájlt.
