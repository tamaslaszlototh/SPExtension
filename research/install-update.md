# Research: plugin telepítése admin jog nélkül és önfrissítés Windowson

Ticket: [#6](https://github.com/tamaslaszlototh/SPExtension/issues/6) · Map: [#1](https://github.com/tamaslaszlototh/SPExtension/issues/1) · Dátum: 2026-11-03

Célkörnyezet: Windows, Painter **11.1.0** (saját gép, admin) és **12.2.0** (céges gép, admin jog nélkül).

Jelölés: **[V]** = elsődleges forrásból ellenőrzött tény (link mellette). **[K]** = következtetés ellenőrzött tényekből. **[?]** = bizonytalan, a célgépen ki kell próbálni.

---

## 1. Hová kell telepíteni a Python plugint?

### Ellenőrzött tények

- **[V]** A felhasználói plugin-gyökér 7.2+ verziótól Windowson `C:\Users\<user>\Documents\Adobe\Adobe Substance 3D Painter`. A régi verziók az `Allegorithmic` mappát használták. ([Create a Python plugin](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/create-a-python-plugin), [Shelf and Assets location](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/pipeline-and-integration/resource-management/shelf-and-assets-location))
- **[V]** A Python pluginok a `python/plugins` almappába kerülnek. A sima `plugins` mappa a **JavaScript** pluginoké. ("Python plugins need to go under the "python/plugins" folder.") ([Create a Python plugin](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/create-a-python-plugin))
- **[V]** Minden plugin-gyökérben három almappa van ([Load external Python plugins](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/load-external-python-plugins)):
  - `plugins`: opcionális komponensek, a Python menüben kapcsolhatók be.
  - `startup`: "Modules that are always loaded at application startup".
  - `modules`: a pluginok közös segédmoduljai.
  - Az ezeken kívül vagy más néven elhelyezett Python fájlokat a Painter figyelmen kívül hagyja.
- **[V]** A keresési útvonal (`substance_painter_plugins.path`) három forrásból áll össze: a `SUBSTANCE_PAINTER_PLUGINS_PATH` környezeti változóból, a Painter telepítési mappájából és a felhasználói erőforrásmappából. A `plugins`, `startup` és `modules` mappák automatikusan bekerülnek a `sys.path`-ba. ([substance_painter_plugins module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/writing-plugins/substance-painter-plugins))
- **[V]** A plugin egy szabványos Python modul, amely `start_plugin()` és `close_plugin()` függvényt ad. A `reload_plugin()` opcionális hook, amely a bezárás után és az újraindítás előtt fut. ([substance_painter_plugins module](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/writing-plugins/substance-painter-plugins))
- **[V]** Egyedi gyökér is megadható a `SUBSTANCE_PAINTER_PLUGINS_PATH` változóval. Ez a három almappát tartalmazó gyökérre mutat. ([Load external Python plugins](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/load-external-python-plugins))
- **[V]** A beállítások és alkalmazásadatok helye (7.2+):
  - Registry: `HKEY_CURRENT_USER\Software\Adobe\Adobe Substance 3D Painter`.
  - Alkalmazásadat: `%LOCALAPPDATA%\Adobe\Adobe Substance 3D Painter` és `%APPDATA%\Adobe\Adobe Substance 3D Painter` (thumbnailek, log).

  ([Preferences and application data location](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/pipeline-and-integration/installation-and-preferences/preferences-and-application-data-location))

### 11.1.0 és 12.2.0 közti különbségek

| | 11.1.0 | 12.2.0 | Forrás |
|---|---|---|---|
| Python | 3.11 (10.1 óta) | **3.13** (12.0.0 óta) | [10.1 notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/old-versions/version-10-1), [12.0 notes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/version-12-0) |
| Qt / PySide6 | Qt 6.5.6 / PySide6 6.5.6 (10.1 óta) | **Qt 6.8.6** (12.0.0 óta) | ugyanott |
| Plugin mappák | `Documents\Adobe\Adobe Substance 3D Painter\python\{plugins,startup,modules}` | ugyanaz | [All changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes) |

- **[V]** A teljes changelog 11.0 és 12.2.x között **nem** jelez változást a plugin-mappa szerkezetében vagy a betöltés módjában. A Python-releváns bejegyzések API-bővítések. Ezek közül 12.0.3: "[Python][Mac] Exceptions in Python console with SSL" (Mac-only fix) és "[Python] Painter crash on exit with leftover Qt widgets". ([All changes](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/release-notes/all-changes))
- **[K]** A két verzió ugyanabból a mappából tölt, így egy telepítési hely mindkettőre jó. A kód csak tiszta Python és PySide6 legyen, `.pyd` vagy natív függőség nélkül, mert a Python ABI eltér (3.11 és 3.13). Ez a pluginokra elég, mert a Python-forrásfájlok mindkét verzión futnak, ha nem használunk 3.12+ szintaxist (pl. PEP 695 `type X = ...`), és ha nincs 3.13-ban eltávolított stdlib modul (pl. `imghdr`, `cgi`, PEP 594).

### Javaslat [K]

- A kód a `python/plugins/<csomag>/` helyre kerüljön, csomagként (mappa `__init__.py`-jal, benne `start_plugin`/`close_plugin`).
  - Alternatíva: `python/startup/`, ha a felhasználónak egyáltalán nem kell bekapcsolnia.
- **[?]** Nem ellenőrzött, hogy a Painter megjegyzi-e a `plugins/` alatti plugin bekapcsolt állapotát újraindítás után. A dokumentáció nem írja le. A `startup/` mappa garantáltan minden induláskor betölt. **Ezt a 12.2-es gépen ki kell próbálni.**
- **[?]** Céges gépen gyakori az OneDrive Known Folder Move: ilyenkor a Documents valójában `C:\Users\<user>\OneDrive - <Cég>\Documents`. Az Adobe-dokumentáció ezt nem tárgyalja. Ezért:
  - A plugin ne égesse be a Documents útvonalat, hanem a saját helyét `__file__`-ból, a gyökeret pedig `substance_painter_plugins.path`-ból vezesse le.
  - A telepítő/útmutató mutassa meg, hova kell másolni. A legegyszerűbb a Painterben: Python menü, majd a plugin mappájának megnyitása, ha van ilyen menüpont, vagy kiírni a `substance_painter_plugins.path` értékét a Python konzolban.

## 2. Hol tároljuk a felhasználói Layout JSON-t, hogy a frissítés ne írja felül?

- **[K]** A Layoutot **a plugin kódmappáján kívül** kell tárolni, mert a frissítés azt a mappát cseréli. Javaslat: `%APPDATA%\SPExtension\layout.json`.
  - Admin jog nélkül írható, ugyanúgy, ahogy a Painter maga is a `%APPDATA%\Adobe\...` alá ír ([Preferences and application data location](https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/pipeline-and-integration/installation-and-preferences/preferences-and-application-data-location)).
  - Pythonból `os.environ["APPDATA"]`. Windowson a kulcsok kis- és nagybetű-érzéketlenek ([os.environ](https://docs.python.org/3/library/os.html#os.environ)).
  - Alternatíva: egy `SPExtension` mappa a Painter Documents-gyökerében, de **nem** a `python/` alatt, mert az ott lévő `.py` fájlokat a Painter modulként kezelheti.
- **[K]** A release-be egy `default_layout.json` kerüljön a kódmappába, csak olvasásra. Első induláskor, ha nincs felhasználói `layout.json`, a plugin átmásolja. A frissítés így csak az alapot cseréli, a felhasználóét soha.
- **[V]** Inno Setup esetén ugyanez deklaratívan is megoldható:
  - `onlyifdoesntexist` flag: "Only install the file if it doesn't already exist on the user's system."
  - `uninsneveruninstall` flag: a fájl eltávolításkor is megmarad.

  ([Inno Setup [Files] section](https://jrsoftware.org/ishelp/topic_filessection.htm))
- **[K]** Atomikus mentés a JSON sérülése ellen: előbb `layout.json.tmp`-be írunk, aztán `os.replace(tmp, dst)`. A CPython doksi szerint létező célfájl esetén "it will be replaced silently if the user has permission", azonos fájlrendszeren ([os.replace, CPython Doc/library/os.rst](https://github.com/python/cpython/blob/3.13/Doc/library/os.rst)). Az atomicitást a doksi POSIX-követelményként említi. Windowson ez gyakorlatilag `MoveFileEx` replace, **[?]** atomicitási garancia nélkül.

## 3. Per-user telepítési opciók

### a) Inno Setup, `PrivilegesRequired=lowest`

- **[V]** `lowest` mellett a Setup nem kér UAC-emelést, és mindig "non administrative install mode"-ban fut. ([PrivilegesRequired](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm))
- **[V]** Non-admin módban ([Non Administrative Install Mode](https://jrsoftware.org/ishelp/topic_admininstallmode.htm), [Constants](https://jrsoftware.org/ishelp/topic_consts.htm)):
  - az uninstall-információ és a HKA a `HKEY_CURRENT_USER` alá kerül;
  - az "auto" konstansok a "user" formára képeznek (`{autopf}` → `{userpf}` = `{localappdata}\Programs`);
  - a `{group}` a felhasználó profiljában jön létre.
- **[V]** Hasznos konstansok: `{userdocs}` ("My Documents"), `{userappdata}` (Roaming), `{localappdata}`. ([Constants](https://jrsoftware.org/ishelp/topic_consts.htm)) A plugin célja tehát: `DefaultDirName={userdocs}\Adobe\Adobe Substance 3D Painter\python\plugins\spextension`.
- **[V]** Ha egy cserélendő fájl zárolva van, a Setup 4-szer újrapróbálja másodperces szünettel, aztán hibát ad. ([Files section, Remarks](https://jrsoftware.org/ishelp/topic_filessection.htm)) A `CloseApplications` a Windows Restart Managerrel érzékeli és bezárja azokat az alkalmazásokat, amelyek a frissítendő fájlokat használják. ([CloseApplications](https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm))
- **[?]** A `restartreplace` flag (csere a következő rendszerindításkor) várhatóan admin jogot igényel, ezért non-admin módban ne számítsunk rá. Az Inno doksi ezen az oldalon ezt nem mondja ki.
- **Fő kockázat céges gépen:** az Inno Setup kimenete egy `.exe`.
  - **[V]** Az AppLocker alapértelmezett exe-szabályai mindenki számára csak a `%windir%\*` és a `%programfiles%\*` alól engedik a futtatást. Mindenhonnan csak a `BUILTIN\Administrators` futtathat. Ráadásul ezek a szabályok minden PE-fájlra vonatkoznak, kiterjesztéstől függetlenül. ([Executable rules in AppLocker](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/applocker/executable-rules-in-applocker))
  - **[K]** Ha a cég AppLockert vagy hasonló szabályt használ, a `Downloads`-ból indított setup.exe **blokkolódik**. Aláíratlan exe-nél SmartScreen-figyelmeztetés is várható **[?]**.

### b) Zip + kézi másolás (vagy Painteren belüli telepítés)

- **[K]** Ez nem futtat exe-t, ezért a céges gépen ez a biztos út. A zip a `spextension/` mappát tartalmazza, amelyet a felhasználó a `python\plugins\` alá másol. Ehhez csak a Documents írási joga kell.
- **[?]** PowerShell/`.bat` telepítőszkript is lehetséges. Céges gépen azonban az ExecutionPolicy, az AppLocker szkript-szabályok vagy a Constrained Language Mode tilthatja. Nem ellenőrizve, ezért nem ajánlott elsődlegesnek.

### Javaslat [K]

Az elsődleges terjesztési formátum a **zip** legyen (ezt az önfrissítés is használja). Az Inno Setup `PrivilegesRequired=lowest` exe opcionális kényelmi csomag lehet a saját gépre. A frissítéshez egyik sem kell, mert azt maga a plugin végzi Pythonból.

## 4. Saját fájlok cseréje, amíg a Painter fut

- **[V]** A CPython import a forrásfájlt megnyitja, beolvassa és azonnal bezárja (`with _io.open_code(path) as file: return file.read()`). A `.py` fájl tehát import után nincs nyitva tartva. ([importlib/_bootstrap_external.py, 3.13](https://github.com/python/cpython/blob/3.13/Lib/importlib/_bootstrap_external.py))
- **[K]** Ebből következik, hogy a tiszta Python plugin `.py` fájljai futás közben is felülírhatók vagy átnevezhetők Windowson. Zárolást a natív bővítmények (`.pyd`/`.dll`) okoznának, ezért ne legyen ilyen a pluginban. A memóriában lévő modulok viszont a régi kódot futtatják tovább, ezért a frissítés **a következő indításkor lép életbe**. Ez illeszkedik a map döntéséhez: "indításkor ellenőrzi és rákérdez".
- **[V]** Elvben lehetséges a forró újratöltés a `substance_painter_plugins.reload_plugin(module)` hívással, de ez csak a fő modult tölti újra. ([API](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/writing-plugins/substance-painter-plugins)) **[K]** Egy több modulból álló csomagnál az almodulok régiek maradnának, ezért v1-ben ne erre építsünk.
- **[K]** Javasolt, biztonságos sorrend:
  1. A zipet a `%LOCALAPPDATA%\SPExtension\staging\<verzió>\` alá töltjük le, és ott bontjuk ki. A `zipfile.extractall` már kiszűri a `..`-t, de a doksi szerint előtte érdemes ellenőrizni a tagokat ([zipfile warning](https://docs.python.org/3/library/zipfile.html#zipfile.ZipFile.extractall)).
  2. Ellenőrzés: a várt fájlok megvannak, a verzió egyezik, és opcionálisan egy SHA-256 is egyezik a release-ben közölt értékkel.
  3. A régi mappát átnevezzük `spextension.old`-ra, az újat a helyére tesszük `os.replace`-szel. Mindkettő azonos köteten van, mert mindkettő a Documents alatt. Hiba esetén visszaállítunk.
  4. Üzenet a felhasználónak: "Frissítve, indítsd újra a Paintert."
  - Ha a Documents OneDrive-on van, a OneDrive-szinkron rövid ideig fogva tarthatja a fájlokat **[?]**. Ilyenkor újrapróbálás kell, vagy a cserét a következő induláskor, a `start_plugin` legelején, importok előtt egy kis bootstrap modul végzi el.
- **[K]** A tisztább változat egy vékony, stabil **bootstrap** modul, amely a `plugins/` alatt ritkán változik. Ez induláskor alkalmazza a stage-elt frissítést, és csak utána importálja a tényleges kódot. Így a csere sosem érint futó kódot.

## 5. Legújabb release lekérdezése a GitHub API-ból

- **[V]** `GET https://api.github.com/repos/tamaslaszlototh/SPExtension/releases/latest` adja vissza "the most recent non-prerelease, non-draft release, sorted by the created_at attribute". A publikált release-ek "available to everyone", így publikus repónál token nem kell. ([Releases API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release))
  - Ajánlott headerek: `Accept: application/vnd.github+json`, `X-GitHub-Api-Version`.
- **[V]** Kötelező a `User-Agent`: "Requests with no User-Agent header will be rejected." ([Getting started](https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api)) **[K]** A `urllib` alapból küld `Python-urllib/3.x` UA-t, de adjunk meg sajátot (pl. `SPExtension/<verzió>`).
- **[V]** A token nélküli rate limit **60 kérés/óra, forrás-IP-nként**. Túllépéskor 403 vagy 429 jön, a `x-ratelimit-*` headerekkel. ([Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api))
  - **[K]** Céges NAT mögött az egész cég egy IP-n osztozhat. Ezért a plugin naponta legfeljebb egyszer ellenőrizzen (az időbélyeget az `%APPDATA%` alá menti), és a 403/429-et csendben, "nincs frissítés-infó"-ként kezelje.
- **[V]** A feltételes kérés (`If-None-Match` + ETag, 304) csak **hitelesített** kérésnél nem számít bele a limitbe. Token nélkül nem spórol limitet. ([Best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api))
- **[V]** Asset letöltése kétféleképpen lehet ([Release assets](https://docs.github.com/en/rest/releases/assets#get-a-release-asset)):
  - a `browser_download_url`-ről;
  - az asset API URL-ről `Accept: application/octet-stream` headerrel. Ez vagy átirányít (302), vagy közvetlenül streamel: "API clients should handle both a 200 or 302 response".
  - **[K]** Az átirányítás egy másik hosztra (GitHub objektumtároló) mutat. Céges proxynál ezt a hosztot is engedni kell, nem csak a `github.com`/`api.github.com`-ot **[?]**.
- **[K]** A verzió-összehasonlításhoz a `tag_name` kell (pl. `v1.2.0`), a plugin pedig a saját verzióját egy `version.py`-ból olvassa. Az asset neve legyen fix minta (pl. `spextension-<ver>.zip`), hogy a plugin az `assets[]`-ből név alapján válasszon.

## 6. Letöltés a Painter Pythonjából: proxy, SSL, céges hálózat

### Proxy

- **[V]** `urllib.request` alapból először a `<scheme>_proxy` környezeti változókat nézi. Ha nincs ilyen, Windowson a registry "Internet Settings" részéből olvas. ([urllib.request.getproxies / ProxyHandler](https://docs.python.org/3/library/urllib.request.html))
- **[V]** A CPython forrás alapján a registry-olvasás csak a `ProxyEnable` + `ProxyServer` (és `ProxyOverride`) értékeket nézi. Az **`AutoConfigURL`-t (PAC-szkript) és a WPAD-ot nem** kezeli. ([CPython Lib/urllib/request.py, getproxies_registry](https://github.com/python/cpython/blob/3.13/Lib/urllib/request.py))
  - **[K]** Ha a céges gép PAC-fájllal konfigurált proxyt használ (gyakori), a `urllib` **közvetlenül** próbál kapcsolódni, és timeout vagy elutasítás lesz belőle.
- **[V]** Proxy-hitelesítésből a `urllib` csak Basic és Digest módot támogat (`ProxyBasicAuthHandler`, `ProxyDigestAuthHandler`). **NTLM/Kerberos (Negotiate) nincs.** ([urllib.request](https://docs.python.org/3/library/urllib.request.html))
  - **[K]** Ha a céges proxy Windows-integrált hitelesítést kér, a tiszta `urllib` 407-et kap.
- **[?]** Lehetséges fallback a PySide6 `QtNetwork` (`QNetworkAccessManager` + `QNetworkProxyFactory.setUseSystemConfiguration(True)`). Ez a Windows rendszer-proxybeállítását használja, akár PAC-ot is, és a Qt ismerheti az integrált hitelesítést is. Nem ellenőrzött, hogy a Painter PySide6-ja tartalmazza-e a QtNetwork modult és TLS backendet. **A 12.2-es gépen tesztelni kell.**
- **[K]** Kezelhető módja: egy rövid timeoutos (pl. 5 s) ellenőrzés. Hiba esetén a plugin nem zavar, csak a menüben jelez ("frissítés-ellenőrzés sikertelen"). Legyen egy kézi beállítás is a proxy URL-re (a `%APPDATA%\SPExtension\settings.json`-ban), végső fallbackként pedig egy "Megnyitás böngészőben" gomb a release oldalra. A böngésző a céges proxyt biztosan kezeli, a zipet a felhasználó tölti le, a plugin pedig "Telepítés zip fájlból" funkcióval veszi át.

### SSL / céges SSL-inspection

- **[V]** `ssl.create_default_context()` → `load_default_certs()`: "On Windows it loads CA certs from the `CA` and `ROOT` system stores." ([ssl](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.load_default_certs)) **[K]** A céges SSL-inspection gyökértanúsítványa, ha a cég a Windows tanúsítványtárba telepítette (ez a szokásos), így a Painter Pythonjában is megbízható. Külön `certifi` nem kell. Sőt, a `certifi` rontana a helyzeten, mert az nem ismeri a céges CA-t.
- **[V]** **11.1 és 12.2 közti fontos különbség:** Python 3.13 óta a `create_default_context()` alapból bekapcsolja a `VERIFY_X509_STRICT` és `VERIFY_X509_PARTIAL_CHAIN` flageket. Ezek "may reject pre-RFC 5280 or malformed certificates". A kikapcsolás módja: `ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT`. ([ssl.create_default_context, "Changed in version 3.13"](https://docs.python.org/3/library/ssl.html#ssl.create_default_context))
  - **[K]** Painter 12.x a Python 3.13-at használja. A **12.2-es céges gépen** tehát egy hibásan generált SSL-inspection CA (pl. hiányzó Authority/Subject Key Identifier vagy nem kritikus basicConstraints) `CERTIFICATE_VERIFY_FAILED` hibát adhat, míg ugyanez a 11.1-en (Python 3.11) működne.
  - Javaslat: első próbálkozás a default contexttel. Ha a hiba kifejezetten X.509-szigorúsági jellegű, egyszer újrapróbálunk `VERIFY_X509_STRICT` nélkül, de a lánc-ellenőrzés marad bekapcsolva. `CERT_NONE`-t soha ne használjunk.
- **[K]** Az integritást a release-ben közölt SHA-256-tal érdemes ellenőrizni (pl. egy `.sha256` asset vagy a release body). Ez akkor is véd, ha valaki gyengíti az SSL-t.

### Blokkolt fájltípusok

- **[K]** A frissítés zipet tölt le és Python fájlokat bont ki, exe nem fut. Ezt az AppLocker exe-szabályai nem érintik, mert azok PE-fájlokra vonatkoznak ([AppLocker executable rules](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/applocker/executable-rules-in-applocker)). **[?]** Céges web-proxy/DLP blokkolhatja a `.zip` letöltését is. Ennek ellenőrzése a barát gépén szükséges.

---

## Összefoglaló javaslat a spec számára [K]

1. Telepítési hely: `{Documents}\Adobe\Adobe Substance 3D Painter\python\plugins\spextension\`. Mindkét Painter-verzió ugyanonnan tölt.
2. Terjesztés: zip GitHub Release assetként. Az első telepítés kézi másolás (rövid útmutatóval). Az Inno Setup `PrivilegesRequired=lowest` opcionális, a céges gépen várhatóan blokkolt.
3. Felhasználói adat: `%APPDATA%\SPExtension\layout.json` (+ `settings.json`, utolsó ellenőrzés időbélyege). A release-ben lévő `default_layout.json` csak az első indításkor másolódik.
4. Frissítés: indításkor, naponta legfeljebb egyszer `releases/latest`. Rákérdezés után letöltés a `%LOCALAPPDATA%\SPExtension\staging` alá, ellenőrzés (SHA-256), mappacsere, majd a következő Painter-indításkor él.
5. Hálózat: `urllib` + Windows tanúsítványtár. Python 3.13-on X509_STRICT-fallback. Hiba esetén csendes kudarc + "megnyitás böngészőben" + "telepítés zip-ből".
6. Kód: tiszta Python, 3.11-kompatibilis szintaxis, natív függőség nélkül.

## Nyitott pontok, a 12.2-es céges gépen kell tesztelni

- [ ] Hol van ténylegesen a Documents (OneDrive KFM?), és ezt a mappát látja-e a Painter (`substance_painter_plugins.path` kiírása a Python konzolban).
- [ ] Megmarad-e a `plugins/` alatti plugin bekapcsolt állapota újraindítás után, vagy `startup/` kell.
- [ ] Működik-e `urllib.request.urlopen("https://api.github.com/repos/tamaslaszlototh/SPExtension/releases/latest")` a Painter konzoljából. Ha nem, mi a hiba: proxy (PAC, 407) vagy SSL (`VERIFY_X509_STRICT`).
- [ ] Elérhető-e a `PySide6.QtNetwork` a Painterben, és működik-e rendszer-proxyval.
- [ ] Letölthető-e `.zip` a céges hálózaton, és elérhető-e a GitHub asset-redirect hosztja.
- [ ] Fut-e egy aláíratlan Inno Setup exe a gépen (AppLocker/SmartScreen).
