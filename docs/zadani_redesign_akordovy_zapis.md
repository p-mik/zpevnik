# Zadání: redesign editoru akordového zápisu (varianta A „Subtilní“)

## Cíl
Předělat **jen vzhled** stránky „Akordový zápis“ (editor akordů písně). Funkčnost, data, URL, endpointy a klávesové zkratky zůstávají beze změny.

Směr:
- přehlednější a méně kostrbaté,
- kompaktnější,
- ostré linie a hranaté kontejnery zůstávají, ale subtilnější,
- část textových tlačítek nahradit ikonami.

Referenční markup mockupu je v přiloženém `reference_mockup_a.html`. Je to formát návrhového nástroje, **nekopírovat 1:1**. Slouží jen jako předloha pro rozměry, barvy a strukturu.

## Postup
1. Najdi šablonu, CSS a JS editoru akordového zápisu. Zjisti, jak jsou dnes vykreslené sekce, řádky, takty a doby a jak fungují repetice a volty.
2. Než začneš měnit kód, napiš krátký plán: které soubory upravíš a co v nich.
3. Implementuj po částech v pořadí sekcí níže (1 → 6). Po každé části se zastav a počkej na potvrzení.
4. Nic nemaž z logiky. Pokud se nějaký prvek přesouvá, třeba levá lišta do toolbaru, zachovej jeho handlery a id nebo data atributy, na které se váže JS.

## Design tokeny (CSS proměnné na `:root`)
```css
--bg:        #efe9db;   /* pozadí stránky */
--paper:     #faf7ef;   /* pozadí sekcí, inputů */
--ink:       #1b1a17;   /* text, hlavní linky */
--hair:      #ddd5c3;   /* jemné dělicí linky uvnitř sekce */
--hair-2:    #c9c1ae;   /* oddělovače v toolbaru, kbd rámeček, přerušované placeholdery */
--dot:       #cfc7b5;   /* značka prázdné doby */
--muted:     #6b665c;   /* sekundární text, neaktivní ikony (kontrast na --bg ~5:1) */
--disabled:  #a39d90;
--accent:    #a4262c;   /* červená: levý pruh stránky, focus buňky, hover „smazat“ */
--teal:      #1f5c55;   /* badge repetice */
--white:     #ffffff;   /* hover pozadí tlačítek, pozadí editované buňky */
```
- **Fonty (Google Fonts):** `Oswald` 400/500/600 pro nadpisy, akordy, tlačítka a čísla. `IBM Plex Sans` 400/500/600 pro UI text. `IBM Plex Mono` 500 pro `kbd`.
- **Rohy:** všude `border-radius: 0`.
- **Linky:** 1px, hlavní v barvě `--ink`, vnitřní v `--hair`. Žádné 2px a silnější rámečky (výjimka: volta 1.5px).
- **Stíny ani gradienty** se nepoužívají.

## 1. Stránka a hlavička
- Levý okraj stránky tvoří pruh `4px solid var(--accent)`, stejně jako dnes. Obsah má padding zhruba `28px 56px 40px` a mezi bloky mezeru `20px`.
- Velký rámeček „Takt / Tempo“ **zrušit**. Hlavička je jeden řádek, flex `space-between`, zarovnaný na spodní hranu:
  - **Vlevo:** nad nadpisem odkaz „← Zpět na píseň“ (12px, `--muted`, šipka jako SVG ikona). Pod ním `h1` s názvem písně (Oswald 600, 30px) a vedle něj na baseline „Akordový zápis · Verze N“ (13px, `--muted`).
  - **Vpravo:**
    - Popisek „TAKT“ (11px, uppercase, letter-spacing .08em, `--muted`) a **segmentový ovladač**: jeden rámeček 1px `--ink` s pozadím `--paper`, tlačítka `2/4 3/4 4/4 6/8 12/8 …` o výšce 30px, oddělená 1px svislou linkou. Aktivní tlačítko má pozadí `--ink` a text `--bg`, hover má pozadí `--white`. Tlačítko „Vlastní…“ se zkracuje na „…“ s `aria-label="Vlastní takt"`.
    - Popisek „BPM“ a input 56×30px, rámeček 1px `--ink`, text Oswald 14px na střed, placeholder „—“.

## 2. Toolbar (místo levé plovoucí lišty)
- Vodorovný pruh výšky 44px s linkou 1px `--ink` nahoře i dole, bez bočních rámečků. Ideálně `position: sticky; top: 0` a pozadí `--bg`.
- Tlačítka jsou 32px vysoká, mají ikonu a krátký popisek (Oswald 13px, uppercase, letter-spacing .04em). V klidu nemají rámeček, na hover dostanou rámeček 1px `--ink` a pozadí `--white`.
- **Skupina 1:** `Repetice`, `Volta`, `Takt` (původně „Změnit takt“).
  - Bez výběru taktů jsou disabled: barva `--disabled`, bez hover efektu.
  - Každé tlačítko má `title` s nápovědou, např. „Repetice (vyber takty)“.
- **Oddělovač:** svislá linka 1×20px v barvě `--hair-2`.
- **Skupina 2:** `Sekce` (původně „+ Přidat sekci“), `Nadpis` (původně „+ Jen nadpis“).
- **Vpravo:** nápověda ke zkratkám jako `kbd` čipy, 11px, `--muted`:
  - `Tab` další buňka
  - `Enter` nový řádek
  - `⌫` spojit s předchozím
  - Styl `kbd`: rámeček 1px `--hair-2`, pozadí `--paper`, padding `1px 5px`, 10px mono.

## 3. Sekce
- Kontejner má rámeček 1px `--ink`, pozadí `--paper` a mezi sekcemi mezeru 14px.
- **Hlavička sekce:** výška 40px, spodní linka 1px `--hair`, flex s mezerou 8px. Zleva doprava:
  1. Šipky nahoru/dolů jako dvě malé chevron ikony nad sebou, každá 22×16px. U první sekce se nezobrazuje šipka nahoru, u poslední šipka dolů (stejně jako dnes).
  2. **Název sekce jako inline editovatelný text, ne input v rámečku.** Oswald 500, 15px, uppercase, letter-spacing .08em. Při hover nebo focusu se objeví přerušované podtržení `1px dashed --disabled`. Prázdný název ukazuje placeholder „Název sekce“ v `--disabled` s přerušovaným podtržením.
  3. Meta info, 11px `--muted`, např. „13 taktů“, u prázdné sekce „prázdná“. Počítat z dat.
  4. **Badge repetice** (přesunutý z patičky sekce): pozadí `--teal`, text `--bg`, výška 20px, Oswald 12px, text „1–12 ×2“ a ikona × pro zrušení (`aria-label="Zrušit repetici"`).
  5. Mezera `flex-grow: 1`.
  6. Ikonová tlačítka 32×32px, v klidu barva `--muted` bez rámečku, na hover rámeček 1px `--ink`, barva `--ink` a pozadí `--white`:
     - **Spojit s předchozí** (ikona „šipka nahoru k lince“), jen u sekcí, které nejsou první,
     - **Duplikovat** (ikona dvou čtverců),
     - **Smazat sekci** (ikona koše), na hover rámeček i ikona v `--accent`.
     - Každé tlačítko má `aria-label` a `title` s původním textem.
- **Tělo sekce:** padding `10px 16px`, mezi řádky mezera 6px.
- **Prázdná sekce:** místo tlačítka „+ Přidat řádek“ se zobrazí klikací placeholder přes celou šířku: výška 44px, `1px dashed --hair-2`, text 12px `--muted` „Začni psát akord, nebo `Enter` pro první řádek“. Klik nebo Enter má stejný efekt jako dnešní „Přidat řádek“.
- **Neprázdná sekce:** pod řádky je malé textové tlačítko „+ řádek“ (11px, uppercase, `--muted`, bez rámečku, hover jako ostatní).
- **Nadpis (Jen nadpis):** nemá box. Je to řádek výšky 36px, obsahuje text (Oswald 13px, uppercase, letter-spacing .14em), za ním vodorovnou linku 1px `--ink` přes zbytek šířky a vpravo ikony posunu a smazání.

## 4. Takty a doby
- **Takt** má pevnou šířku zhruba 216px a výšku řádku 40px. Obsahuje 4 doby v gridu `repeat(4, minmax(0,1fr))`, případně podle taktu (3/4 → 3, 6/8 → 6 atd., podle dnešní logiky).
- **Taktové čáry:** každý takt má `border-left: 1px solid --ink` a za posledním taktem v řádku je uzavírací čára 1px. **Zrušit** dnešní svislé mezery a podtržení pod každou buňkou.
- **Akord:** Oswald 500, 19px, zarovnaný dole vlevo (padding `0 0 9px 8px`).
- **Prázdná doba:** jen vodorovná čárka 10×1px v barvě `--dot`, bez podtržení celé buňky.
- **Křížky pro smazání taktu** (dnešní × v rohu) skrýt a zobrazovat jen na hover taktu, barva `--muted`.
- **Editovaná buňka (focus):** rámeček 1px `--accent` s vnitřním odsazením ~4px, pozadí `--white` a textový kurzor v `--accent`.
- **Volta:** nad taktem je pruh výšky 16px (rezervovat ho u všech taktů, aby řádky nelítaly). Volta = `border-top` a `border-left` 1.5px `--ink`, číslo „1.“ / „2.“ v Oswald 11px, pravý okraj 8px.
- **Repetice:** skutečné notové značky místo samotného badge.
  - Začátek: tenká čára a dvě tečky 3×3px (`‖:`).
  - Konec: dvě tečky a čára (`:‖`).
  - Badge v hlavičce sekce zůstává kvůli zrušení a počtu opakování.
- **Řádek** může mít víc taktů než 4 (volta 2 v témže řádku), takže řádek je `display:flex; align-items:flex-end`.
- **„Nová sekce od tohoto řádku“:** místo textu ikonové tlačítko s nůžkami 32×32 napravo od řádku (`title` a `aria-label` s původním textem). V klidu je vidět jen na hover řádku, u touch zařízení vždy.

## 5. Ikony
Inline SVG, `viewBox="0 0 16 16"`, `fill="none"`, `stroke="currentColor"`, `stroke-width="1.5"`, `stroke-linecap="square"`. Tvary cest:

| Ikona | Cesta |
|---|---|
| zpět | `M13 8H3M7 4L3 8l4 4` |
| nahoru / dolů | `M3 11l5-5 5 5` / `M3 5l5 5 5-5` |
| spojit s předchozí | `M3 2.5h10M8 14V6M5 9l3-3 3 3` |
| duplikovat | `<rect x="5" y="5" width="8.5" height="8.5"/>` + `M2.5 10.5V2.5h8` |
| smazat | `M3 4h10M6 4V2.5h4V4M4.5 4l.7 9.5h5.6l.7-9.5` |
| nůžky | kruhy `cx=4 cy=4 r=2`, `cx=4 cy=12 r=2` + `M5.6 5.2L14 12M5.6 10.8L14 4` |
| přidat sekci | `<rect x="2" y="3" width="12" height="10"/>` + `M8 6v4M6 8h4` |
| nadpis | `M3 3h10M8 3v10` |
| plus | `M8 3v10M3 8h10` |
| × | `M4 4l8 8M12 4l-8 8` |
| repetice | `viewBox 0 0 20 16`: `M2 2v12M4.5 2v12M15.5 2v12M18 2v12` + 4 tečky r=.9 na (7.5,6) (7.5,10) (12.5,6) (12.5,10) |
| volta | `M2 14V3h12` + text „1.“ (Oswald 7px) |
| takt | text „3“ nad „4“ (Oswald 7px) oddělené `M3 8.5h10` |

Ikony dej do jednoho partialu nebo include, ať se nekopírují.

## 6. Přístupnost a detaily
- Všechna ikonová tlačítka jsou skutečné `<button>` s `aria-label`.
- Focus ring pro klávesnici: `outline: 1px solid var(--ink); outline-offset: 1px`.
- Kontrast textu minimálně 4.5:1. Na `--bg` nepoužívat nic světlejšího než `--muted`, kromě placeholderů a disabled stavů.
- Nepřidávat emoji, zaoblené rohy ani stíny.

## Akceptační kritéria
- Všechny dnešní akce fungují stejně: přidání, mazání, přesun, duplikace a spojení sekcí, přidání řádku, rozdělení sekce, repetice, volta, změna taktu, tempo i klávesové zkratky.
- Stránka nemá horizontální scroll při šířce 1280px. Řádek se 4 takty se vejde i s tlačítkem nůžek.
- Sekce Intro se 4 takty má na výšku maximálně ~110px (dnes ~160px).
- Levá plovoucí lišta zmizela a vše z ní je v toolbaru.
- Žádný rámeček není silnější než 1px (kromě volty).
