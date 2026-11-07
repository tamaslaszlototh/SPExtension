# Anchor pointok és a Fill content tesztelése (Shelf+ v0.8.3-rc.1)

Ez a verzió három dolgot hoz:

- Az **anchor point** Step megtartja a nevét. A felvétel mindig elmenti a végső nevet (a Painter alapértelmezett „Anchor point” nevét is), lejátszáskor ezzel a névvel jön létre, és a szerkesztőben átírható.
- Egy Fill channel **forrása lehet egy anchor point**, a neve alapján: egy új Fill layeren, egy layeren belüli Fillen és egy maszk Filljén is.
- Új Step: **Fill content**. Egy **meglévő** layer channeleit kapcsolja be vagy ki, és egy meglévő Fill layer tartalmát (anchor point, szín, érték, resource vagy egy material) állítja be. A felvétel is ilyen Step-et készít, ha egy meglévő layer channeleit vagy tartalmát módosítod.

A Shelf+ felülete angol, ezért a gombok és feliratok nevét angolul írjuk, ahogy a képernyőn látod.

Kérlek, a teszteket **mindkét gépen** egyszer futtasd le:

- **Otthon:** Painter 11.1.0
- **Munkahelyen:** Painter 12.2.0, admin jog nélkül

Egy kör kb. 15 perc. Az eredményeket a [végén lévő táblázatba](#eredmények) írd.

## 1. A verzió telepítése

1. Zárd be a Paintert.
2. Töltsd le a **ShelfPlus-v0.8.3-rc.1.zip** fájlt a [v0.8.3-rc.1 kiadás oldaláról](https://github.com/tamaslaszlototh/SPExtension/releases/tag/v0.8.3-rc.1).
3. Nyisd meg a `Documents\Adobe\Adobe Substance 3D Painter\python\plugins` mappát. Ha van benne már `ShelfPlus` mappa, töröld.
4. Másold be a zipből a `ShelfPlus` mappát ebbe a `plugins` mappába.
5. Indítsd el a Paintert, és nyiss meg egy projektet. Olyan projekt másolatát használd, amelynek nem baj, ha megváltozik.
6. Kattints a Panel jobb felső sarkában a **☰** gombra. Az első sornak ezt kell mutatnia: **Shelf+ v0.8.3**.
   - Ha régebbi verziót mutat, vagy a Painter azt írta, hogy „Shelf+ v0.8.3 failed to start; reverted to …”, itt állj meg.
   - Kattints a **☰ → Copy diagnostics** menüpontra, és küldd el, amit kimásol.

A saját Layoutod megmarad. A teszt néhány új Buttont ad hozzá, ezeket a végén törölheted.

**Előkészítés:** a projektben legyen egy **meglévő Fill layer** és egy **meglévő anchor point** (bármelyik layer tartalmában vagy maszkjában; jobb klikk a layeren → *Add anchor point*). Jegyezd fel az anchor point nevét.

## 2. A tesztek

### A. Meglévő Fill layer forrása egy meglévő anchor point

1. Jelöld ki a meglévő Fill layert. Egy Group sorában kattints a **+ → Recorded Workflow** pontra. Megjelenik a piros **● REC** sáv.
2. A Fill layer tulajdonságainál kattints a **BaseColor**-ra, nyisd meg az **Anchor points** fület, és válaszd ki a meglévő anchor pointot.
3. Kattints a **Stop** gombra.
   - ✅ Megjelenik egy **Start** blokk (vagy egy *select layer* blokk) egy **Fill content** Step-pel. A sorában ez áll: **BaseColor anchor “<név>”**.
   - ✅ A Step-re kattintva a **Content** alatt **Per channel** látszik, és a BaseColor mellett **Anchor point**, az anchor point nevével.
4. Mentsd a Workflow-t.
5. Vond vissza a változtatást a Painterben (**Ctrl+Z**), jelöld ki ugyanazt a Fill layert, és kattints egyszer az új csempére.
   - ✅ A BaseColor újra az anchor pointot használja.

### B. Egy elnevezett anchor point és egy rá hivatkozó Fill layer

1. Indíts egy új felvételt (**+ → Recorded Workflow**).
2. Adj egy **anchor pointot** bármelyik layerhez, és nevezd át **Edges**-re.
3. Adj hozzá egy **Fill layert**, és a **Height** forrásának válaszd az **Edges**-t (*Anchor points* fül).
4. Kattints a **Stop** gombra.
   - ✅ Az anchor point sorában **Anchor point “Edges”** áll.
   - ✅ A Fill layer sorában **anchor “Edges”** áll.
   - ✅ Az anchor point Step-re kattintva a **Name** mezőben **Edges** áll.
5. Mentsd. Vond vissza a felvétel összes változtatását a Painterben (az Edges anchor pointnak el kell tűnnie), jelölj ki egy layert, és kattints az új csempére.
   - ✅ Létrejön az Edges anchor point és a Fill layer, a Height pedig az Edges-t használja.
6. Kattints rá **másodszor** is.
   - ✅ Semmi nem változik, és a Panel ezt írja: *An anchor point named “Edges” already exists.*

### C. Fill content kézzel

1. Egy Group sorában kattints a **+ → Workflow button** pontra, majd a szerkesztőben a **+ Add Step → Setting → Fill content** pontra.
   - ✅ A Step sorában ⚠ jelzés van, és a **Save** gomb nem aktív, amíg nem választasz semmit.
2. A **Channels** alatt a **Roughness** mellett válaszd az **Off**-ot.
3. A **Content** legyen **Per channel**, és a **BaseColor** mellett válaszd az **Anchor point**-ot. A listában a projekt anchor pointjai szerepelnek; válaszd ki az egyiket.
4. Mentsd. Jelöld ki a meglévő Fill layert, és kattints az új csempére.
   - ✅ A Roughness channel kikapcsol, a BaseColor az anchor pointot használja, a többi channel nem változik.
5. Jelölj ki egy **Paint layert**, és kattints újra a csempére.
   - ✅ Semmi nem változik, és az üzenet végén ez áll: *needs a Fill layer.*

### D. Ami továbbra sem kerül bele

1. Indíts egy felvételt. Egy meglévő layeren belüli **Fill effectnek** (nem Fill layernek) változtasd meg a tartalmát.
   - ✅ A Panel ezt írja: *Changing an existing effect cannot be recorded, so it was skipped.* Kattints a **Stop**, majd a **Cancel** gombra.

**Fontos:** a tesztek végén mindenképp kattints a **☰ → Copy diagnostics** pontra, és küldd el a kimásolt szöveget **akkor is, ha minden sikerült**. Benne van, hogyan olvasta ki a Shelf+ az anchor pointot a Painterből. Ezt a Painter nélkül nem tudtuk ellenőrizni.

## Eredmények

Írd be: **Pass**, vagy **Fail** egy rövid megjegyzéssel arról, mi történt. A **Notes** oszlopba írj be mindent, ami furcsa volt, akkor is, ha a teszt sikerült.

| Teszt | Otthon (11.1.0) | Munkahely (12.2.0) | Notes |
|---|---|---|---|
| 1. Telepítés: a ☰ v0.8.3-t mutat | | | |
| A. Meglévő Fill layer → anchor point forrás, felvétel és futtatás | | | |
| B. „Edges” elsőre lefut, másodszor nem indul | | | |
| C. Fill content kézzel; Paint layeren „needs a Fill layer” | | | |
| D. Fill effect módosítása: üzenet, nincs Step | | | |
| Copy diagnostics elküldve | | | |

**Ha valami nem sikerül:**

1. Rögtön kattints a **☰ → Copy diagnostics** pontra, még a Painter újraindítása előtt.
2. Másold be, amit kimásol, az üzenetedbe. Benne vannak a verziók és a napló legutóbbi sorai.

A kitöltött táblázatot küldd vissza, például hozzászólásként a [#35-ös issue-hoz](https://github.com/tamaslaszlototh/SPExtension/issues/35).

A teljes Recording tesztleírás (A–H tesztek) itt található: [recording.hu.md](recording.hu.md).
