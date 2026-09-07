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
