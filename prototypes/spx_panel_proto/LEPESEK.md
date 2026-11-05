# SPX Panel prototípus – lépések (kb. 20–30 perc)

Ez egy **eldobható próba**. Semmit nem hajt végre a Painterben: a gombokra kattintva csak egy felirat jelenik meg alul.
Azt kell eldöntenünk, hogyan nézzen ki a Panel, és hogyan szerkeszd rajta a gombokat.
Három változat van, ezeket próbáld ki egymás után: **A**, **B** és **C**.

Elég **egy gépen** kipróbálni, mindegy, melyiken (11.1 vagy 12.2).

📝 = ezt írd fel, ezt kérem vissza.

## 1. Telepítés

1. Csomagold ki a `spx_panel_proto.zip`-et. Egy `spx_panel_proto` mappát kapsz.
2. Másold a mappát ide (ha már van ilyen nevű mappa, előbb töröld):
   `Dokumentumok\Adobe\Adobe Substance 3D Painter\python\plugins\spx_panel_proto\`
3. Indítsd el a Paintert, és nyiss meg egy tetszőleges projektet.
4. **Python → spx_panel_proto**: pipáld be. Megjelenik egy „SPX Panel (prototípus)” ablak.
   - Ha nem jelenik meg: **Python → Reload Plugins Folder**, majd pipáld be újra.
5. Nyisd meg az **Assets** ablakot is (**Window → Views → Assets**).

A Panel alján egy **sárga sáv** van. Ez nem része a tervnek, csak ezzel váltasz a változatok között:
**◀ / ▶** (vagy a ← / → billentyűk, ha a Panelen van a fókusz). A **{ }** gomb a háttérben tárolt adatokat mutatja; ezzel nem kell foglalkoznod.

## 2. Mindhárom változatnál ugyanezt csináld

Minden változatnál végezd el az alábbiakat, és közben figyeld, mennyire kényelmes.

1. **Hover és kattintás:** vidd az egeret néhány gombra (megjelenik a neve?), és kattints rájuk (alul kiírja, mi „történt”).
2. **Dokkolás:** dokkold a Panelt a jobb szélre, majd az aljára (vízszintes csíknak), végül hagyd **lebegni**. Mindegyik helyzetben méretezd át **keskenyre, szélesre és alacsonyra** is.
3. **Brush hozzáadása:** húzz be egy brusht az **Assets** ablakból a Panelre. Próbáld ki egy sima **tool presettel** (pl. Basic Hard), és ha találsz, egy **.abr / „Brush” típusúval** is.
4. **Új Workflow és Menu button:** a „+” menüvel adj hozzá egyet-egyet. A Menu buttonnál a listában a Painter saját menüparancsai vannak, ikonnal.
5. **Átrendezés:** tegyél egy gombot máshová.
6. **Törlés:** törölj egy gombot.

### A – Rács + szerkesztő mód
- A gombok rácsban vannak, és sorokba tördelődnek, ahogy a Panel szélessége engedi.
- Szerkesztéshez kattints jobb fent a **✎** gombra. Ilyenkor a gombokat **húzással** rendezed, a **×** töröl, a **+** csempével adsz hozzá újat. Kilépés: **Kész** vagy **Esc**.

### B – Eszköztár + listaszerkesztő
- Egyetlen sor gomb, **elválasztókkal**. Ha a Panel széles, vízszintes, ha magas, függőleges. Ami nem fér ki, a **»** menübe kerül.
- Szerkesztéshez kattints a **⚙** gombra (vagy jobb klikk a sávon → **Layout szerkesztése…**). Ekkor egy **lista** jelenik meg: húzással rendezed, dupla klikkel átnevezed, a **+ Új** gombbal elválasztót is tehetsz be. A végén **Mentés** vagy **Mégse** (ilyenkor minden változás elvész).

### C – Csoportok, mindig szerkeszthető
- **Elnevezett csoportok** (pl. Brushok, Rétegek, Fájl), amelyek a nevükre kattintva összecsukhatók.
- **Nincs külön szerkesztő mód.** A gombokat bármikor átrakhatod húzással, akár másik csoportba is. Törléshez húzd a lent megjelenő **piros kukába**, utána pár másodpercig **Visszavonás** gomb látszik.
- Jobb klikk egy gombon: átnevezés, áthelyezés, törlés. Jobb klikk egy csoport nevén: átnevezés, sorrend, új csoport, törlés. A csoport sorában lévő **+** gombbal oda adsz hozzá új gombot.

## 3. Visszajelzés – ezt kérem vissza

📝 Másold be és töltsd ki:

```
Painter verzió:
1. Melyik változat tetszett a legjobban, és miért?
2. Van-e olyan, ami egy másik változatból jó ötlet, és át kéne venni? (pl. csoportok, elválasztók, » menü, kuka + Visszavonás)
3. Hova dokkolnád a Panelt a mindennapi munkában (jobb oldal / alsó csík / lebegve / máshova)?
4. Kell-e külön szerkesztő mód (A, B), vagy jobb, ha mindig húzható (C)? Volt-e, hogy véletlenül arrébb húztál egy gombot, amikor csak kattintani akartál?
5. Elég-e csak az ikon + hover név, vagy kellene néha felirat is a gomb alá?
6. Csempeméret: jó a mostani, vagy legyen kisebb/nagyobb (esetleg állítható)?
7. Kb. hány gombot használnál egyszerre a Panelen (5? 15? 40?)
8. Behúzás: sikerült-e tool presetet behúzni? És .abr / Brush típusút? Kéne-e az utóbbi?
9. Ha az Assets ablak zárva van, a Brush button nem tud brusht váltani (az aktiváláshoz látszania kell). Mit szeretnél ilyenkor:
   (a) a gomb kinyitja az Assets ablakot, és utána vált,  (b) üzenetet ír, hogy nyisd ki,  (c) más: …
10. Bármi más, ami zavart vagy hiányzott:
```

📎 Küldd vissza ezt a fájlt is: `%APPDATA%\spx_panel_proto\naplo.txt` (írd be a Windows Intéző címsorába).
Ha tudsz, csatolj 1-2 **képernyőképet** is a Panelről a kedvenc helyén és méretében.

## 4. Eltávolítás

Pipáld ki: **Python → spx_panel_proto**. Utána törölheted a `plugins\spx_panel_proto` mappát.
