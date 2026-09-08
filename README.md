# Zpěvník — zadání aplikace

## Jak to spustit lokálně

Vyžaduje Docker Desktop.

```bash
cp .env.example .env   # a uprav hodnoty (SECRET_KEY, DB_PASSWORD, ...)
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Appka poběží na `http://localhost:8007/`, admin na `http://localhost:8007/admin/`.

Frontend se builduje v rámci Docker image (multi-stage build) a servíruje ho Django přes
WhiteNoise — není potřeba spouštět `npm run dev` zvlášť, pokud jen ověřuješ, že appka běží.
Pro vývoj frontendu s hot reloadem: `cd frontend && npm install && npm run dev`.

Migrace se generují **pouze lokálně** (`python manage.py makemigrations`) a commitují —
nikdy ne na serveru ani v deploy pipeline.

---

## API endpointy (fáze 1a)

Autentizace: Django session (`SessionAuthentication`) + CSRF. Frontend musí u
POST/PUT/PATCH/DELETE posílat hlavičku `X-CSRFToken` (hodnota z cookie `csrftoken`,
kterou nastaví `GET /api/auth/me/`). Bez platného tokenu vrací zápis `403`.

Výchozí oprávnění je `IsAuthenticated` — pokud tabulka níže nepíše jinak, je endpoint
jen pro přihlášené. Role `admin` = `is_staff`, role `člen` = běžný přihlášený uživatel.
Seznamové endpointy jsou stránkované (`page`, `page_size`, výchozí 50 na stránku).

**Zatím bez `Session` a `Anotace` — to je fáze 2.**

### Auth

| Cesta | Metoda | Kdo smí | Vrací |
|---|---|---|---|
| `/api/auth/login/` | POST | kdokoliv | uživatele po přihlášení (`username`, `password` v těle) |
| `/api/auth/logout/` | POST | přihlášený | `204` |
| `/api/auth/me/` | GET | kdokoliv | `{authenticated, id, username, role}` — `role` je `admin` nebo `clen`; nastavuje CSRF cookie |

### Písně (`/api/pisne/`)

| Metoda | Kdo smí | Poznámka |
|---|---|---|
| GET (list) | přihlášený | lehký seznam `{id, kod, nazev, interpret}` pro rychlý scroll; `?kod=123` přesná shoda, `?search=text` (název/interpret), `?ordering=kod` |
| GET (detail) | přihlášený | + `verze` (všechny verze písně) a `aktivni_verze` (podle logiky auto-loadu níže, pro přihlášeného uživatele) |
| POST / PUT / PATCH / DELETE | admin | |

### Verze písní (`/api/verze-pisni/`)

| Metoda | Kdo smí | Poznámka |
|---|---|---|
| GET | přihlášený | `?pisen=<id>`, `?stav=`, `?vlastnik=` |
| POST | přihlášený | člen vždy vytvoří `stav=personal` s `vlastnik=` sebou — cokoliv jiného pošle klient v `stav`/`vlastnik`, server přepíše |
| PUT / PATCH / DELETE | admin (cokoliv), vlastník (jen svoje `personal`) | ostatní členové dostanou `403` |
| GET `/api/verze-pisni/<id>/soubor/` | admin, vlastník `personal`, jinak každý přihlášený | samotné PDF (viz „Servírování souborů“) |

Cesta k souboru na disku se v API **nikdy nevrací** — místo pole `soubor` je jen
`ma_soubor` (bool) a `puvodni_nazev_souboru` (popisek). K obsahu se jde výhradně
přes chráněný endpoint výše.

#### Upload PDF

`POST`/`PATCH` na `/api/verze-pisni/` s `multipart/form-data`, pole `soubor`.

- Běžnou verzi (`draft`/`download`/`confirmed`/`handmade`) nahraje **admin**;
  **personal verzi kdokoliv přihlášený** (server dosadí `stav=personal` a `vlastnik`
  podle volajícího, ať klient pošle cokoliv).
- Validuje se **obsah, ne přípona** — soubor musí začínat magic bytes `%PDF-`.
  PNG přejmenovaný na `.pdf` skončí `400`.
- Limit velikosti je `MAX_UPLOAD_SIZE` (výchozí 25 MB, přes env `MAX_UPLOAD_SIZE_MB`).
  Nginx má vlastní `client_max_body_size 200m`, ale na ten se nespoléháme.
  Prázdný soubor je odmítnut.

**Co uživatel uvidí při moc velkém souboru — pozor při psaní frontendu.**
Jsou dva různé limity a každý se chová jinak:

| Velikost | Kdo odmítne | Odpověď |
|---|---|---|
| do 25 MB | — | projde |
| 25–200 MB | Django | `400` + JSON `{"soubor": ["Soubor je příliš velký (limit je 25 MB)."]}` (ověřeno) |
| nad 200 MB | nginx | `413` + **HTML stránka nginxu, ne JSON** |

Frontend tedy nesmí u chyby uploadu slepě dělat `response.json()` — u `413` přijde HTML
a parsování spadne. A protože se v obou případech soubor nejdřív celý nahraje na server
a teprve pak odmítne, má smysl velikost zkontrolovat rovnou v prohlížeči
(`input.files[0].size`) a velký soubor vůbec neposílat.
- **Jméno souboru na disku generuje server** (`verze/<rok>/<měsíc>/<uuid>.pdf`), jméno
  od klienta se do cesty nedostane vůbec — path traversal je tím vyloučený
  konstrukčně, ne filtrováním. Původní jméno se ukládá zvlášť, očištěné na holý
  basename, jen pro zobrazení.

### Složky, zpěvníky, setlisty

| Cesta | Metoda | Kdo smí | Poznámka |
|---|---|---|---|
| `/api/slozky/` | GET | přihlášený | |
| `/api/slozky/` | POST/PUT/PATCH/DELETE | admin | |
| `/api/zpevniky/` | GET | přihlášený | vč. lehkého seznamu `pisne`; `verejny_token` vidí jen admin (viz níže) |
| `/api/zpevniky/` | POST/PUT/PATCH/DELETE | admin | zápis přes `pisne_ids` (seznam ID písní) |
| `/api/setlisty/` | GET/POST/PUT/PATCH/DELETE | přihlášený | sdílený zdroj kapely (viz níže); vnořené `polozky` (`pisen`, `poradi`) se zapisují spolu se setlistem |
| `/api/polozky-setlistu/` | GET/POST/PUT/PATCH/DELETE | přihlášený | pro drobné úpravy pořadí bez přepsání celého setlistu |

**`verejny_token` je v API čitelný jen pro admina** (`is_staff`) — pro ostatní přihlášené
je pole vždy `null`, ať jde o detail nebo seznam. Je to sdílitelný odkaz na veřejný
zpěvník, ne informace, kterou má vidět kdokoliv přihlášený.

**Setlisty jsou vědomě sdílený zdroj kapely, ne osobní vlastnictví jednotlivce.**
Model `Setlist` nemá pole `vlastnik` a kterýkoliv přihlášený člen smí upravit
i setlist založený někým jiným — kapela má společný repertoár a vlastnictví
setlistů by přidalo práva navíc bez reálného užitku. Pokud se v praxi ukáže,
že si lidé chtějí dělat vlastní soukromé setlisty, přidá se pole `vlastnik`
a odpovídající oprávnění později (analogicky k `VerzePisne.vlastnik`).

### Veřejný zpěvník — bez přihlášení (`/api/verejny/<token>/`)

| Cesta | Metoda | Kdo smí | Vrací |
|---|---|---|---|
| `/api/verejny/<token>/` | GET | kdokoliv | `{nazev, pisne: [{kod, nazev, ..., aktivni_verze, soubor_url}]}` |
| `/api/verejny/<token>/pisen/<kod>/soubor/` | GET | kdokoliv | PDF té písně |

Jen tento zpěvník a jeho písně — žádná ID, žádní uživatelé, žádné `personal` verze,
žádné jiné zpěvníky. Neplatný nebo chybějící token → `404`.

Token se **negeneruje automaticky** — v adminu je u zpěvníku akce
**„Vygenerovat veřejný odkaz (token)“** (`secrets.token_urlsafe`, ne `uuid4`).
Zpěvník bez tokenu je přes tento endpoint nedostupný.

⚠️ **`verejny_token` musí být `NULL`, nikdy prázdný řetězec.** Pole je
`unique=True, null=True`, takže „nemá token“ smí být jen `NULL` — dvě `""` hodnoty
by spadly na unique constraintu a druhý zpěvník bez tokenu by nešel uložit.
Django formuláře (a tedy i admin) ale do `CharField` ukládají prázdný vstup jako `""`,
proto to `Zpevnik.save()` normalizuje zpátky na `None`. **Tu normalizaci při refaktoru
nevyhazuj** — bez ní se to rozbije tiše a až u druhého zpěvníku bez odkazu.

**Jak je zajištěné, že veřejný odkaz neotevře celou knihovnu.** Soubor se adresuje
jako „píseň s kódem K ve zpěvníku s tokenem T“, ne jako „verze s ID X“. Klient tedy
nikdy neříká, kterou verzi chce — vybírá ji server. Řetěz kontrol:

1. `token` → právě jeden zpěvník; neplatný, odvolaný nebo chybějící token = `404`,
2. píseň se hledá **jen mezi písněmi toho zpěvníku** (`zpevnik.pisne`), takže píseň
   z jiného zpěvníku přes tenhle token nejde získat, i když veřejná je,
3. verzi vybere `aktivni_verze(user=None)`, která pro nepřihlášeného z principu
   `personal` verze vynechává — plus explicitní pojistka navíc přímo ve view.

Kdyby v URL bylo ID verze, stačilo by uhodnout ID cizí `personal` verze u písně,
která ve veřejném zpěvníku je. Proto tam není. Píseň, která má jen `personal` verzi,
dostane ve výpisu `soubor_url: null` a její soubor přes token nejde stáhnout (`404`).

### Servírování souborů (`X-Accel-Redirect`)

Django soubory **neposílá samo** — streamování by na celou dobu přenosu zablokovalo
gunicorn worker. Místo toho ověří práva a vrátí prázdnou odpověď s hlavičkou
`X-Accel-Redirect: /protected/<cesta z DB>`; soubor pak ze složky pošle nginx:

```nginx
location /protected/ {
    internal;
    alias /opt/zpevnik/media/;
}
```

`internal` znamená, že `/protected/` **nejde zavolat zvenčí** — jen jako důsledek
`X-Accel-Redirect` z Djanga. Tím pádem každý přístup k notám projde kontrolou práv.

Dvě věci, které tenhle mechanismus tiše obejdou, a proto tu nejsou:

- **žádný `location /media/` v nginx vhostu** — servíroval by stejné soubory bez
  jakékoliv kontroly (ověřeno v `our-hub/infra/nginx/zpevnik.upupaepops.cz.conf`),
- **žádné `static(MEDIA_URL, ...)` v `config/urls.py`**, ani pod `if settings.DEBUG`.

Cesta v hlavičce se skládá výhradně z `verze.soubor.name` (hodnota z databáze),
nikdy z parametru requestu — klient ovlivní jen to, o kterou verzi si řekne.

Pro lokální vývoj bez nginx existuje přepínač `X_ACCEL_REDIRECT=False`, kdy soubor
pošle Django přes `FileResponse`. **V produkci musí zůstat `True`** — když je vypnutý
a zároveň `DEBUG=False`, `manage.py check` skončí chybou `zpevnik.E001`.

### Mazání souborů

**Smazání verze písně soubor na disku nemaže.** Je to vědomé rozhodnutí: mazání
v adminu je jeden neopatrný klik a PDF nahrané na zkoušce nemusí být kde vzít znovu,
takže okamžité mazání by zbytečně vyrábělo nevratné ztráty. Osiřelé soubory ale
místo zabírají (server na tom s diskem není dobře), tak se uklízejí zvlášť:

```bash
docker compose exec web python manage.py uklid_souboru            # jen vypíše
docker compose exec web python manage.py uklid_souboru --smazat   # opravdu smaže
```

Bez `--smazat` jen vypíše, co by smazal. Maže soubory, na které neukazuje žádná verze
a které jsou starší než `--dny` (výchozí 30) — ten odklad je právě to okno na
„vrať to zpátky“. Stejně se uklidí i soubory nahrazené novým uploadem.

**Zatím ZÁMĚRNĚ není v cronu.** Nejdřív ať appka pár měsíců běží a uvidí se, kolik toho
reálně osiří — pak se rozhodne, jestli to cronovat a jak často. Do té doby je to ale
příkaz, na který si za tři měsíce nikdo nevzpomene, takže: **vedeno jako TODO
v `our-hub/infra/STATE.md`**, ne jako hotová věc. Stav se dá kdykoliv zjistit
spuštěním bez `--smazat`.

### Logika auto-loadu verze (`Pisen.aktivni_verze(user)`)

1. uživatelova nejnovější `personal` verze, jinak
2. nejnovější `confirmed` verze, jinak
3. nejnovější verze vůbec (nikdy cizí `personal`, u nepřihlášených žádná `personal`)
4. pokud píseň nemá žádnou verzi → `None`

---

> Pracovní název: **zpevnik** (finální název TBD, subdoména `<nazev>.upupaepops.cz`)
> Stav: zadání po brainstormingu, před implementací
> Verze: 1.0 (2026-07-21)

---

## Vize

Webová aplikace pro správu a čtení zpěvníků kapely (a víc kapel). Členové mají přístup k PDF písním s metadaty, čtou je na tabletu (Android i iPad), dělají si vlastní poznámky a na zkoušce/koncertě se synchronizují přes živou session řízenou kapelníkem.

**Co appka JE:** zpěvník + čtečka + session + osobní poznámky.
**Co appka NENÍ:** správa financí kapely, plánování akcí, mailing, notový editor. Scope creep zakázán.

---

## Role a přístup

| Role | Práva |
|------|-------|
| admin | správa uživatelů, oprávnění, všech zpěvníků a písní |
| člen | čtení zpěvníků, vlastní poznámky/verze, účast v session, tvorba setlistů |
| veřejnost | jen čtení zpěvníku přes veřejný odkaz (QR), bez přihlášení |

- Přihlášení přes Google (django-allauth, OAuth).
- Granulární práva per složka/zpěvník = odloženo do fáze 3. Pro MVP stačí tři role výše.
- Veřejný zpěvník: view bez auth pod neuhodnutelným URL tokenem. Read-only.

---

## Datový model (koncept)

### pisen (kmenová píseň)
- `kod` — číselný kód písničky (pro rychlé vyhledání v session)
- `nazev`
- `interpret`
- `tonina` (volitelné)
- `capo` (volitelné)
- `tempo` — BPM, int, nullable (pro vizuální metronom)
- `odkaz_nahravka` — URL na YouTube/Spotify („takhle to hrajeme")
- pozn.: píseň sama o sobě nemá obsah — obsah nesou verze

### verze_pisne
- `pisen` — FK na kmenovou píseň
- `typ_obsahu` — **pdf | text** (text = příprava na budoucí ChordPro, teď se implementuje jen pdf)
- `soubor` — PDF (u typu pdf)
- `stav` — draft / download / confirmed / handmade / personal
- `vlastnik` — FK na uživatele, povinné jen u stavu personal
- `vytvoreno`, `upraveno` — automatické timestampy
- Verze se rozlišují automaticky (FK + vlastník + timestamp), žádné ruční číslo verze.

**Logika auto-loadu verze:** uživateli se otevře (1) jeho nejnovější personal verze, jinak (2) confirmed, jinak (3) cokoliv nejnovějšího.

### zpevnik
- `nazev`, `slozka` (stromová struktura složek)
- `verejny_token` — pro veřejný odkaz (nullable)
- M2M na písně (píseň může být ve víc zpěvnících, ve zpěvníku je vždy kmenová píseň, ne konkrétní verze)

### setlist
- Trvalé pojmenované pořadí písní (příprava na koncert, k projetí doma, k tisku).
- Nezávislý na session — session ho jen „přehrává".

### session
- Živý kanál: kapelník + členové.
- `aktualni_pozice`, FK na setlist (volitelně — jde jet i bez setlistu, ad hoc listováním).

### anotace
- `verze_pisne` (nebo kmenová píseň + user), `vlastnik`, `data` — JSON pole objektů:
  - `textbox` — volné textové pole
  - `akord` — textové pole ve stylu akordu
  - `tab_grid` — 4–6 řádků × N sloupců, monospace, prázdná buňka = pomlčka (datově 2D matice znaků)
  - `znacka` — předdefinovaný badge (REF, SL., SPECIAL, … — číselník TBD)
- Každý objekt má pozici (x, y, strana PDF). PDF zůstává netknuté, poznámky jsou overlay vrstva.

---

## Moduly a fáze

### Fáze 1 — MVP (použitelné na zkoušce)

- [ ] Auth přes Google + tři role
- [ ] Zpěvníky + složky, CRUD
- [ ] Upload jednotlivých PDF s metadaty
- [ ] Čtečka PDF optimalizovaná na tablet
- [ ] **Stage mode** — fullscreen bez UI, tmavé pozadí, tap vpravo/vlevo = listování
- [ ] Vyhledávání: kód / název / rychlý scroll seznamem
- [ ] Veřejný odkaz na zpěvník (QR)
- [ ] Django admin pro správu metadat a uživatelů

### Fáze 2 — session a poznámky

- [ ] Setlisty (trvalé, tisknutelné)
- [ ] Session přes **polling** (interval 2–3 s): kapelník listuje, členům se přepíná; „další song" jede podle setlistu
- [ ] Personal verze: nahrání vlastního PDF místo úprav
- [ ] Anotační vrstva nad PDF: textbox, akord, tab_grid, značky (React, PDF.js)
- [ ] Vizuální metronom — u písně s vyplněným `tempo` se zobrazí klikací spoušť; po kliknutí naskočí overlay s blikajícím metronomem, po X vteřinách (nebo N taktech) sám odezní (CSS opacity fade)
      - **Motor: Web Audio API** s lookahead schedulerem (~25 ms), NE `setInterval` (driftuje, zpomaluje na pozadí)
      - Zvuk = zdroj pravdy (přesný audio klok), vizuál = follower přes `requestAnimationFrame` porovnávající audio čas s naplánovanými tiky
      - Volitelný slyšitelný klik (přepínač) — oko synchronizuje hůř než ucho; motor tam je stejně
      - iOS Safari: audio init až v kliknutí (gesto), ne dřív
      - Čistě frontend komponenta, backend nic neřeší

### Fáze 3 — tvorba a komfort

- [ ] Modul Tvorba — stejné anotační nástroje na prázdném plátně (detailní zadání dodá Peťo později)
- [ ] ChordPro text + akordy → PDF přes weasyprint (odemkne transpozici)
- [ ] Poloautomatický batch split velkých PDF (náhledy stránek + naklikání hranic; nejdřív mrknout na vzorový dokument — možná půjde plný automat skriptem)
- [ ] Granulární práva per složka/modul

### Nice to have (bez termínu)

- [ ] Podpora footswitch pedálu (Bluetooth pedál = klávesnice, stačí keydown listener v čtečce)
- [ ] Transpozice (jen pro textový obsah, `[Ami]` → `[Hmi]`; pro PDF principiálně nemožná)
- [ ] Autoscroll
- [ ] Tagy, filtrování podle tóniny
- [ ] Export/tisk setlistu s obsahem

### Vyřazeno

- ~~Offline režim~~ — nebude se používat, škrtnuto
- ~~Notový zápis~~ — nahrazeno: noty se řeší nahráním hotového PDF

---

## Stack a architektura

**Rukopis pattern:** Django 5 + DRF backend, React + Vite frontend (SPA), PostgreSQL, Docker Compose, GitHub Actions deploy, Nginx reverse proxy.

Důvody: anotační vrstva a session UI jsou hustě interaktivní (React dle pravidla hubu); Django admin zdarma pokryje půlku admin modulu; deploy pipeline už je vyladěná z Rukopisu.

**Nové věci oproti Rukopisu:**

1. **File upload + storage** — media volume, PDF v `/opt/<appka>/media/`
2. **Auth-chráněné servírování PDF** — Nginx `X-Accel-Redirect`: Django ověří práva, Nginx pošle soubor. (Django nesmí streamovat soubory samo — pomalé; Nginx nesmí servírovat media bez auth kontroly.)
3. **PDF.js** na frontendu (čtečka + canvas overlay pro anotace)
4. **django-allauth** (Google OAuth) — prerekvizita: založit OAuth credentials v Google Cloud Console (consent screen atd.)

**Session:** polling, žádné WebSockets. Bez Redis, bez Channels, bez ASGI migrace. Latence 2–3 s je pro „kapelník otočil stránku" v pohodě. WebSockets jen kdyby to reálně skřípalo.

---

## Infrastruktura — prerekvizity a rizika

| Věc | Stav |
|-----|------|
| Port | 8007+ (dle pravidla STATE.md; před přiřazením `docker ps \| grep 80`) |
| Disk | ⚠️ server na 80 % (7,4 GB volných). PDF jsou malé (stovky kB), ale před nasazením úklid nebo upgrade disku |
| Google OAuth | nutno založit credentials v Google Cloud Console (zdarma, klikací opruz) |
| Backup | přidat novou DB do `/opt/backup/db_backup.sh` + media složku do zálohy (PDF nejsou v DB!) |
| iPad | testovat čtečku v Safari — hlavní cílové zařízení vedle Android tabletů |

---

## Otevřené otázky

1. Finální název appky (a subdoména)
2. Číselník předdefinovaných značek pro anotace (REF, SL., SPECIAL, … co dál?)
3. Vzorový dokument pro batch split — poslat, posoudí se automatizovatelnost
4. Detailní zadání modulu Tvorba (dodá Peťo ve fázi 3)

<!-- deploy test: 2026-09-07 22:28:33 -->
