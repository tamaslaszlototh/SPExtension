# SPX Workflow szerkesztő prototípus – lépések (kb. 40–50 perc)

Ez egy **eldobható próba**. Azt kell eldöntenünk, hogyan hozz létre és javíts egy **Workflow**-t a Panelen.
A Workflow **rögzítéssel** készül: elindítod, kattintgatsz a Painterben, a végén Stop, és a Panel összeállítja a lépéseket (Step-eket). Utána javítasz rajta, és elmented gombként.

Három változat van, mindhármat próbáld ki: **A**, **B** és **C**. A különbség: hol látod a rögzítést, és hol javítod a listát.

Fontos:
- A rögzítés **valódi**: figyeli, mit csinálsz a Painterben.
- **A kész Workflow gomb nem hajt végre semmit**, csak alul kiírja, mit csinálna.
- **Elég egy gépen** kipróbálni, mindegy, melyiken (11.1 vagy 12.2).

📝 = ezt írd fel, ezt kérem vissza.

## 1. Telepítés

1. Csomagold ki a `spx_workflow_proto.zip`-et. Egy `spx_workflow_proto` mappát kapsz.
2. Másold a mappát ide (ha már van ilyen nevű mappa, előbb töröld):
   `Dokumentumok\Adobe\Adobe Substance 3D Painter\python\plugins\spx_workflow_proto\`
3. Indítsd el a Paintert, és nyiss meg egy **eldobható projektet** (File → New, egyszerű mesh). A próbában mentés is lesz, ezért ne éles projektet használj.
4. **Python → spx_workflow_proto**: pipáld be. Megjelenik egy „SPX Workflow (prototípus)” ablak.
   - Ha nem jelenik meg: **Python → Reload Plugins Folder**, majd pipáld be újra.
5. Dokkold a Panelt oda, ahová a mindennapi munkában tennéd (pl. jobb oldalra).
6. Legyen látható a **Layers** és az **Assets** ablak is.

A Panel alján van egy **sárga sáv**. Ez nem része a tervnek, ezzel váltasz a változatok között: **◀ / ▶**.
Amíg egy Workflow szerkesztése folyik, a váltás le van tiltva: előbb nyomj **Mentés**t vagy **Mégse**-t.

A Panelen már van négy minta Workflow gomb a „Rétegek” csoportban. Az újakat a **„Saját”** csoportba tedd.

## 2. Mindhárom változatnál ugyanezt csináld

Minden változat elején válassz ki egy layert a Layers ablakban.

### 2.1 Rögzítés

1. A „Saját” csoport sorában kattints a **+** gombra, majd: **● Új Workflow rögzítéssel**.
2. Most a Painterben csináld végig, sorban:
   1. Adj hozzá egy **Fill layert**.
   2. Adj hozzá **fekete maszkot** (Add black mask).
   3. Tegyél a maszkra egy **generatort**, és válassz ki neki egyet (pl. Dirt).
   4. Állítsd a layer **blend módját Multiply**-ra.
   5. Húzd a **layer opacity** csúszkáját kb. 50-re. Ez a layer opacity-je, nem a brushé.
   6. **Fess egy vonást** bárhová. Ennek **nem** szabad Stepként bekerülnie.
   7. Adj hozzá egy **Levels**-t, majd nyomj **Ctrl+Z**-t. A Levelsnek el kell tűnnie a listából.
   8. Nyomj **Ctrl+S**-t (mentés).
   9. Húzz egy **smart maskot** az Assets ablakból a layerre.
3. Közben figyeld, hogyan jelennek meg a Step-ek a Panelen.
4. Nyomd meg a **Stop**-ot.

### 2.2 Javítás

1. A **smart masknál** figyelmeztetés lesz (⚠ kiválasztandó), mert a rögzítés nem látja, melyik smart mask volt. Válaszd ki a Stepet, és **húzd be a beállításába** ugyanazt a smart maskot az Assets ablakból.
2. Adj hozzá egy **Brush** Stepet: húzz be egy brusht az Assets ablakból (A: a listára, B: a szerkesztőablakba, C: a csempesorra). Ezt a rögzítés nem látja, ezért kézzel kell.
3. Adj hozzá egy **Menüparancs** Stepet: **+ Step** (B-ben az „A végén” rész **+** gombja, C-ben a sor végi **+**) → **Menüparancs**. A beállításában próbáld ki az **„Elkapás a menüből”** gombot, aztán kattints a Painter menüjében egy parancsra (pl. File → Export textures). Ha megnyílik a parancs ablaka, csak zárd be.
4. Próbáld meg a **Brush** Stepet a lista **elejére** tenni. Ezt nem szabad engednie, mert a Brush, a menüparancs és a mentés csak a Workflow végén állhat.
5. Cserélj fel két layer Stepet (pl. a Blendet és az Opacity-t).
6. Törölj egy Stepet.
7. Nevezd át a Workflow-t.
8. **Mentés**. A gomb megjelenik a „Saját” csoportban.

### 2.3 Utána

1. Vidd az egeret az új gombra (látszik a neve és a Step-ek?), majd kattints rá (alul kiírja, mit csinálna).
2. Jobb klikk a gombon → **Szerkesztés…** Módosíts valamit, majd **Mentés**.
3. **+ → Új Workflow kézzel**: rakj össze 2–3 Stepet rögzítés nélkül, aztán **Mégse**.
4. Hasonlítsd össze a gombok **ikonját** a Panelen. Változatonként más az automatikus ikon:
   - **A**: az első Step ikonja,
   - **B**: 2×2 kis ikon az első négy Stepből,
   - **C**: a fő Step ikonja + a Step-ek száma.

### A – Panelen belül
- Rögzítéskor a Panel tetején **piros sáv** van, alatta nő a lista.
- Stop után ugyanott javítasz: fent a név, középen a lista, alatta a kijelölt Step beállításai.
- A **● Folytatás** gombbal tovább rögzíthetsz.

### B – Lebegő REC-sáv + külön ablak
- Rögzítéskor egy **kis lebegő sáv** jelenik meg a Painter tetején (arrébb húzható). Rajta van a Step-ek száma és az utolsó Step.
- Stop után egy **külön szerkesztőablak** nyílik. Két táblázat van benne: **„Layer-rész”** és **„A végén”**, jobbra a kijelölt Step beállításai.
- A **● Rögzítés folytatása** gombbal tovább rögzíthetsz.

### C – Idővonal-csempék
- Rögzítéskor a Panel tetején **csempék** sorakoznak: Fill layer → Fekete maszk → … ┃ a végén: Mentés.
- Stop után: kattints egy csempére, és **lebegő beállító** nyílik. Átrendezni a csempék **húzásával** vagy a ◀ ▶ gombokkal lehet.
- A névre **dupla kattintással** nevezed át.

## 3. Visszajelzés – ezt kérem vissza

📝 Másold be és töltsd ki:

```
Painter verzió:
1. Melyik változat tetszett a legjobban, és miért?
2. Van-e olyan, ami egy másik változatból jó ötlet, és át kéne venni?
3. Rögzítés közben: elég jól látszott, hogy rögzítés megy (piros sáv / lebegő sáv / csempék)? Zavart valami?
4. A rögzített lista: minden bekerült, aminek kellett? Bekerült olyan, aminek nem kellett volna?
   (Írd le, mi volt a listában Stop után, vagy küldj róla képernyőképet.)
5. Ctrl+Z rögzítés közben: eltűnt a Levels a listából?
6. Javítás: melyik volt a legkényelmesebb?
   lista + alatta beállítás (A) / táblázat külön ablakban (B) / csempe + lebegő beállító (C)
7. Érthető volt, hogy a Brush, a menüparancs és a mentés csak a végén lehet? Zavart, hogy a Ctrl+S a végére ugrott?
8. A smart mask pótlása (behúzás a beállításba) egyértelmű volt?
9. Brush behúzása a Workflow-ba sikerült? A menüparancs elkapása sikerült?
10. Név: jó az automatikus név (pl. „Fill layer + Fekete maszk + Dirt”), vagy mindig magad adnál nevet?
11. Gomb-ikon: melyik a legjobb (A: első Step, B: 2×2, C: fő Step + szám)? Meg tudtad különböztetni a gombokat?
12. Használtad a „Folytatás” gombot? Kellene?
13. Bármi más, ami zavart vagy hiányzott:
```

📎 Küldd vissza ezt a fájlt is: `%APPDATA%\spx_workflow_proto\naplo.txt` (írd be a Windows Intéző címsorába).
Ebből látom, mit rögzített a Panel, és mit hagyott ki.
Ha tudsz, csatolj **képernyőképet** mindhárom változatról Stop után, a kijavítandó listával.

## 4. Eltávolítás

Pipáld ki: **Python → spx_workflow_proto**. Utána törölheted a `plugins\spx_workflow_proto` mappát.
