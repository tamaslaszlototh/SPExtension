# SPX Recording Probe – kiértékelés (fejlesztőnek)

Ticket: [Prototype: Recording mérése a layer stack eseményekkel mindkét gépen](https://github.com/tamaslaszlototh/SPExtension/issues/18) · Alap: [research/workflow-recording.md](https://github.com/tamaslaszlototh/SPExtension/blob/research/workflow-recording/research/workflow-recording.md), „Bizonytalan, mérendő pontok”.

A riport (`rec_<verzió>.txt`) minden lépést `=== LÉPÉS Sxx … KEZDŐDIK / VÉGE` közé zár. A lépés végén lévő összesítő mutatja: hány `LayerStacksModelDataChanged` (LSMDC) jött és mikor, hány diff jött eseményből, és hány **esemény nélkül** (poll vagy lezárás: ez a kimaradt esemény jele), mi lett ADDED/REMOVED/CHANGED, továbbá az ACTION/MENU/KEY/DOCK TITLE jelek és a History utolsó sorai. A fájl végén egy táblázat van.

| Mérendő pont | Lépés(ek) | Mit nézz | Mit dönt el |
|---|---|---|---|
| 1. LSMDC gyakoriság / kiváltók | S01, S02, S11, S13, S16, S18–S21, S24 | `LSMDC` darab és időpontok; `d_pol > 0` = kimaradt esemény | Kell-e polling a Recording alatt, és milyen debounce. Ha S11 alatt sok esemény jön, összevonás kell; ha csak elengedéskor, nem. S16: festés-zaj mértéke. |
| 2. Létezik-e az esemény 11.1-en | fejléc | `hasattr(event, LayerStacksModelDataChanged)` | Kell-e tisztán polling 11.1-en. |
| — callback szála | fejléc | `callback szál == GUI szál` | QTimer-debounce biztonságos-e közvetlenül. |
| — snapshot költség | minden DIFF | `snapshot=… ms, node=…` | Milyen gyakori polling engedhető meg. |
| 3. Generator/Filter: előbb üres? | S07, S08 | `ADDED … "source": null`, majd `CHANGED ….source: None -> resource://…` külön diffben | A „függő Step” kezelés kell-e. |
| 4. Smart material neve | S14 | `NÉV-EGYEZÉS … True/False`, a behúzott név vs. az ADDED GroupLayer neve | A név szerinti heurisztika működik-e, vagy mindig a felhasználó választ. |
| 4. Smart mask mintázata | S15 | ADDED lista (maszk + effektek? folder?), `has_mask` változás | Felismerhető-e a „Smart mask (válassz)” Step. |
| 5. Uid undo után | S17–S21 | `!! UID VISSZATÉRT` vagy `!! ÚJ UID egy eltűnt helyén` | Az undo-kezelés uid alapján mehet-e („pontos fordított diff”). |
| 6. Undo/Redo QAction | KÖRNYEZET, S18–S21 | `UNDO/REDO/SAVE-szerű action`; S18/S19-ben `ACTION triggered 'Undo'` vagy csak `KEY Ctrl+Z` | Undo felismerése action-ből, vagy csak diffből. S21: a History-kattintás látszik-e bárhogy. |
| 7. Tool-jel | S22, S23 | `DOCK TITLE` változás, `ACTION`/`KEY` toolváltáskor; S23-ban bármi jel | Lehet-e „Brush Step hozzáadása?” javaslat, vagy a Brush Step tisztán kézi. |
| 8. History olvasható-e | KÖRNYEZET, minden lépés vége | `HISTORY dock … belső widget-osztályok` (QQuick* = QML), `HISTORY … utolsó sorok` | Kiegészítő jel lehet-e a History szövege. |
| Menu button létrehozása | S25, S26, S27 | `MENU triggered File/Save`, `ACTION triggered` menüből és Ctrl+S-ből; almenü (S27) | A Menu button „kattints a Painter menüjében” létrehozása működik-e, almenüvel is. |
| Kimaradt (nem katalógus) | S13, S28, S29 | átnevezés/törlés/átrendezés diffje | A „kimaradt” jelzés felismerhető-e. |
| Texture set / projekt | S24, S30 | `AKTÍV STACK VÁLTOZOTT`, `ProjectEditionLeft`/`AboutToClose` | Recording leállítás / új alap-snapshot. |
