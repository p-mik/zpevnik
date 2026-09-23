"""Generuje PDF akordového zápisu, schéma 2 (viz
PC_zpevnik_akordovy_zapis_upravy.md a navazující opravy).

reportlab, NE weasyprint — ten by potřeboval systémové knihovny navíc v
Docker image. Fonty jsou přibalené v repu (zpevnik/fonts/, viz LICENSE.md
tam), žádné systémové — jinak by vzhled záležel na tom, co je zrovna
nainstalované na serveru.

Kreslí se přímo přes nízkoúrovňové Canvas API (ne platypus/flowables) —
mřížka akordů s ručním umisťováním potřebuje přesnou kontrolu pozic.

ŘÁDEK = ŘÁDEK. Appka sama nikdy nezalamuje — jak je řádek napsaný v
editoru, tak vyjde v PDF.

ZAROVNÁNÍ DO MŘÍŽKY: šířka doby se neurčuje uvnitř taktu, ale pro každou
POZICI doby v řádku (0-based, napříč VŠEMI takty toho řádku) — je to max
potřebné šířky na téhle pozici ve všech řádcích, co na ni sahají (viz
`_sirky_pozic`). Taktové čáry jsou tak ve stejné svislici napříč CELÝM
DOKUMENTEM (mřížka je SPOLEČNÁ pro VŠECHNY řádky dokumentu, ne jen pro
jednu stránku — viz `vygeneruj_pdf`): takt na pozici (0..3) má všude
stejnou šířku. Kratší řádek prostě skončí dřív, pozice si šířku drží dál
pro ostatní řádky, co na ni sahají. Prázdná doba se nikdy nerozšiřuje
(jen nese tečku); obsazená se rozšíří, jen když by se do základní šířky
nevešel její akord (žádné lokální zmenšování písma, žádné přetékání do
sousední doby).

Stránka je A4 NA ŠÍŘKU (landscape) — dřív se sdílená mřížka omezovala jen
na jednu stránku (s měkkým prahem na scale), protože mřížka sdílená přes
celý dokument u husté písně jako Africa (26 řádků, akordy typu
G#m7/D#m7) srážela scale na ~0.57, i když žádný jednotlivý řádek sám o
sobě tak široký nebyl. Landscape dává asi 1,4× šířky obsahu navíc oproti
portrétu, což tenhle problém řeší přímo (viz report u příslušného
committu pro čísla) — proto teď stačí jedna mřížka pro celý dokument,
žádné dělení podle scale. Stránkování (`_rozvrhni_stranky`) řeší JEN
výšku — scale je pro celý dokument jeden a stejný na všech stránkách.

SEKCE BEZ ŘÁDKŮ (`radky: []`, jen nadpis — typicky rozdělením editoru,
kdy se smaže úplně poslední takt) se v `_radky_s_metadaty` zploští na
položku typu "nadpis" místo "radek": kreslí se jen jméno sekce, žádná
mřížka. `_seskup_pro_zalomeni` hlídá, aby takový osamocený nadpis
nezůstal na konci stránky odtržený od obsahu, co po něm hned následuje.
"""

import io
import os

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

FONT_AKORD = "Carlito-Bold"
FONT_POPISEK = "DejaVuSans"
FONT_POPISEK_TUCNE = "DejaVuSans-Bold"

_fonty_zaregistrovany = False


def _zaregistruj_fonty():
    global _fonty_zaregistrovany
    if _fonty_zaregistrovany:
        return
    pdfmetrics.registerFont(TTFont(FONT_AKORD, os.path.join(FONTS_DIR, "Carlito-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_POPISEK, os.path.join(FONTS_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(
        TTFont(FONT_POPISEK_TUCNE, os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf"))
    )
    _fonty_zaregistrovany = True


# --- rozměry (body, A4 na šířku = 842 x 595) — svislé rozměry (výšky
# řádků, velikosti písma apod.) kalibrované na referenční
# africa_chord_chart.pdf (portrét), viz commit historie; na landscape se
# mění jen šířka obsahu, ne tyhle ---
SIRKA_STRANKY, VYSKA_STRANKY = landscape(A4)
OKRAJ = 30
SIRKA_GUTTERU = 70  # levý sloupec se sekcí
POCET_TAKTU_NA_RADEK = 4  # cíl: 4 takty VÝCHOZÍHO taktu na řádek, vždy

VYSKA_RADKU = 28  # výška řádku PŘI scale=1
MEZERA_RADKU_STEJNA_SEKCE = 4  # mezi dvěma řádky TÉŽE sekce
MEZERA_MEZI_SEKCEMI = 18  # mezi poslední řádkou jedné sekce a první další — ZNATELNĚ víc než
# MEZERA_RADKU_STEJNA_SEKCE, ať jsou sekce opticky oddělené (zvlášť důležité u sekce bez
# řádků, viz "nadpis" v _radky_s_metadaty — tam kromě samotného nadpisu nic jiného
# hranici sekce nenaznačuje, žádná mřížka)
MEZERA_PRO_BADGE = 11  # NAVÍC před řádkem, který má aspoň jeden takt s vlastním taktem
CHORD_BASELINE_OFFSET = 19  # od horního okraje řádkového pásu
SEKCE_BASELINE_OFFSET = 18
BADGE_NAD_RADKEM_OFFSET = 3  # badge sedí NAD y_radku (v mezeře navíc), ne v pásu samotném

VELIKOST_TITULKU = 26  # hlavička SE NEŠKÁLUJE
VELIKOST_INTERPRETA = 13
VELIKOST_SEKCE = 11
VELIKOST_AKORDU = 17.5
VELIKOST_REPETICE_N = 16
VELIKOST_BADGE_TAKTU = 7
VELIKOST_VOLTA_CISLO = 8

# --- volta (bod 5 PC_zpevnik_akordy_ovladani.md) — hranatá závorka nad
# takty, kreslená ve STEJNÉ rezervované mezeře nad řádkem jako badge
# vlastního taktu (MEZERA_PRO_BADGE — "zvětši mezeru jako u označení
# vlastního taktu", viz zadání), jen v jejím HORNÍM pásmu, ať se
# nepotkává s badge textem (ten sedí blíž k y_radku, BADGE_NAD_RADKEM_OFFSET) ---
VOLTA_CARA_NAD_RADKEM_OFFSET = 9  # vodorovná čára závorky nad y_radku
VYSKA_VOLTA_NOHY = 6  # délka svislé "nohy" na koncích závorky
TLOUSTKA_VOLTY = 1.2
# "Žádná spodní hranice velikosti písma" — tohle NENÍ čitelnostní minimum,
# jen technická pojistka proti nulové/záporné velikosti.
TECHNICKY_MIN_VELIKOST = 1
TECHNICKY_MIN_SCALE = 0.02

TLOUSTKA_CARY = 0.8
TLOUSTKA_REPETICE = 2.2
TLOUSTKA_PRAVITKA = 1.2

BARVA_SEDA = (0.3, 0.3, 0.3)
BARVA_CERNA = (0, 0, 0)

REZERVA_MEZI_AKORDY = 5  # mezera připočtená k šířce textu při rozšiřování doby

# --- rezervovaný prostor pro značky repetice (bod 1 PC_zpevnik_akordy_ovladani.md:
# značka konce/začátku repetice nesmí přepsat sousední akord) — stejný princip
# jako REZERVA_MEZI_AKORDY/_sirka_doby, jen navíc VŽDY na SDÍLENÉ pozici doby
# (viz _mezery_znacek_repetice), aby taktové čáry zůstaly v jedné svislici i
# u řádků bez vlastní repetice na dané pozici ---
SIRKA_ZNACKY_ZACATEK_REPETICE = 14  # čára + 2 tečky '|:' PŘED prvním taktem repetice
ODSTUP_ZNACKY_KONCE_OD_CARY = 8  # mezera mezi čárou ':|' a textem '×N'
ODSTUP_ZA_ZNACKOU_KONCE = 6  # mezera ZA '×N', než začne obsah dalšího taktu

Y_ZACATEK_OBSAHU = VYSKA_STRANKY - OKRAJ - 95  # y hned pod pravítkem hlavičky


def _efektivni_takt(takt_v_radku, takt_vychozi):
    return takt_v_radku.get("takt") or takt_vychozi


def _velikost_pro_text(text, font, dostupna_sirka, zakladni_velikost, min_velikost):
    """Zmenšuje TEXT LABELU (sekce, badge — ne akordy, viz zadání bod 5:
    lokální zmenšování akordů je zrušené), dokud se nevejde do dostupné
    šířky. Použito pro název sekce v gutteru: krátké (INTRO, SLOKA) se
    nezmenší vůbec, dlouhé nebo volně psané ano — gutter má pevnou šířku."""
    velikost = zakladni_velikost
    while velikost > min_velikost and pdfmetrics.stringWidth(text, font, velikost) > dostupna_sirka:
        velikost -= 0.5
    return max(velikost, min_velikost)


def _sirka_doby(text, sirka_doby_zakladni, velikost_akordu):
    """Šířka JEDNÉ doby POTŘEBNÁ pro tenhle text — základní, pokud je
    prázdný nebo se do ní akord vejde, jinak přesně tak široká, aby akord
    i s rezervou sedl celý (akord nesmí zasahovat do sousední doby, žádné
    přetékání). Tohle je jen "kolik by tahle jedna buňka potřebovala" —
    výslednou šířku POZICE (v rámci stránky) počítá `_sirky_pozic`."""
    if not text:
        return sirka_doby_zakladni
    potrebna = pdfmetrics.stringWidth(text, FONT_AKORD, velikost_akordu) + REZERVA_MEZI_AKORDY
    return max(sirka_doby_zakladni, potrebna)


def _flat_bunky(radek):
    """Zploštěný seznam buněk celého řádku napříč VŠEMI jeho takty — to je
    "pozice doby v řádku" z modulového docstringu, na kterou navazuje
    zarovnání do mřížky (stejná pozice = stejná šířka ve všech řádcích,
    co na ni sahají)."""
    bunky = []
    for t in radek["takty"]:
        bunky.extend(t["bunky"])
    return bunky


def _pozice_zacatku_taktu(radek, index_taktu):
    """Flat pozice (index do _flat_bunky) první doby daného taktu v řádku."""
    return sum(len(t["bunky"]) for t in radek["takty"][:index_taktu])


def _sirky_pozic(radky, sirka_doby_zakladni, velikost_akordu):
    """Šířka KAŽDÉ POZICE doby v řádku — max potřebné šířky na téhle
    pozici mezi `radky` (viz modulový docstring — volající předává jen
    řádky JEDNÉ STRÁNKY, ne celý dokument). Vrací list délky nejdelšího
    řádku (v dobách); kratší řádky při vykreslování prostě použijí jen
    svůj prefix."""
    max_pozic = max((len(_flat_bunky(r)) for r in radky), default=0)
    sirky = [sirka_doby_zakladni] * max_pozic
    for radek in radky:
        for p, text in enumerate(_flat_bunky(radek)):
            sirky[p] = max(sirky[p], _sirka_doby(text, sirka_doby_zakladni, velikost_akordu))
    return sirky


def _mezery_znacek_repetice(polozky_radek, velikost_repetice_n):
    """Pro KAŽDOU pozici doby (flat index, stejné indexování jako
    `_sirky_pozic`/`_flat_bunky`) spočítá rezervovanou šířku VLEVO
    (začátek repetice, `|:` PŘED prvním taktem) a VPRAVO (konec
    repetice, `:|` + `×N` ZA posledním taktem) — viz zadání bod 1.
    `polozky_radek` jsou položky typu "radek" (viz `_radky_s_metadaty`)
    CELÉHO dokumentu (mřížka je sdílená pro celý dokument, ne po
    stránkách, viz modul docstring) — i řádek BEZ vlastní repetice na
    dané pozici dostane stejně širokou buňku, jinak by taktové čáry
    nebyly v jedné svislici.

    Repetice, co ZAČÍNÁ a KONČÍ na STEJNÉ pozici, nastat nemůže —
    repetice v jedné sekci se nesmí překrývat (viz `validate` v
    serializers.py), takže sousední repetice se vždycky liší aspoň o
    jeden takt a jejich pozice se nikdy nepotkají ve stejném indexu."""
    vlevo = {}
    vpravo = {}
    for polozka in polozky_radek:
        radek = polozka["radek"]
        sekce = polozka["sekce"]
        od_g, do_g = polozka["od_g"], polozka["do_g"]
        for rep in sekce.get("repetice", []):
            if od_g <= rep["od_taktu"] < do_g:
                takt_lok = rep["od_taktu"] - od_g
                p = _pozice_zacatku_taktu(radek, takt_lok)
                vlevo[p] = max(vlevo.get(p, 0.0), SIRKA_ZNACKY_ZACATEK_REPETICE)
            if od_g <= rep["do_taktu"] < do_g:
                takt_lok = rep["do_taktu"] - od_g
                p = _pozice_zacatku_taktu(radek, takt_lok) + len(radek["takty"][takt_lok]["bunky"]) - 1
                text = f"×{rep['krat']}"
                potreba = (
                    ODSTUP_ZNACKY_KONCE_OD_CARY
                    + pdfmetrics.stringWidth(text, FONT_POPISEK_TUCNE, velikost_repetice_n)
                    + ODSTUP_ZA_ZNACKOU_KONCE
                )
                vpravo[p] = max(vpravo.get(p, 0.0), potreba)
    return vlevo, vpravo


def _rozsir_sirky_pro_znacky(sirky_pozic, mezery_vlevo, mezery_vpravo):
    """Nová kopie `sirky_pozic` s přičtenými rezervami z
    `_mezery_znacek_repetice` — `sirky_pozic` samotné (výstup
    `_sirky_pozic`) zůstává nedotčené, ať se nemusí přepočítávat."""
    vysledek = list(sirky_pozic)
    for p, sirka in mezery_vlevo.items():
        if p < len(vysledek):
            vysledek[p] += sirka
    for p, sirka in mezery_vpravo.items():
        if p < len(vysledek):
            vysledek[p] += sirka
    return vysledek


def _najdi_scale(polozky_radek, sirka_obsahu, dob_vychozi):
    """Iterativně najde největší `scale` (<=1), při kterém se nejširší
    řádek MEZI `polozky_radek` (počítaný přes sdílené šířky pozic, viz
    _sirky_pozic, ROZŠÍŘENÉ o rezervy pro značky repetice, viz
    _mezery_znacek_repetice) vejde do šířky stránky. Rozšíření dob
    závisí na velikosti písma, ta na scale — proto iterace, ne jeden
    výpočet. `polozky_radek` jsou položky typu "radek" (viz
    _radky_s_metadaty) — repetice indexují takty přes `sekce`/`od_g`/
    `do_g`, ne přes holý seznam řádků.

    Nejširší řádek = řádek s NEJVÍC pozicemi: šířky pozic (chordové i
    rezervy značek) jsou max/součet přes `polozky_radek`, takže součet
    za víc pozic je vždycky >= součet za míň pozic (všechny členy jsou
    kladné) — stačí sečíst CELÉ pole, není potřeba porovnávat řádek po
    řádku."""
    if not polozky_radek:
        return 1.0

    radky = [p["radek"] for p in polozky_radek]
    zakladni_sirka_doby_pri_1 = sirka_obsahu / (POCET_TAKTU_NA_RADEK * dob_vychozi)
    scale = 1.0
    for _ in range(40):
        sirka_doby_zakladni = zakladni_sirka_doby_pri_1 * scale
        velikost_akordu = max(VELIKOST_AKORDU * scale, TECHNICKY_MIN_VELIKOST)
        velikost_repetice_n = max(VELIKOST_REPETICE_N * scale, TECHNICKY_MIN_VELIKOST)
        sirky_pozic = _sirky_pozic(radky, sirka_doby_zakladni, velikost_akordu)
        mezery_vlevo, mezery_vpravo = _mezery_znacek_repetice(polozky_radek, velikost_repetice_n)
        sirky_pozic = _rozsir_sirky_pro_znacky(sirky_pozic, mezery_vlevo, mezery_vpravo)
        nejsirsi = sum(sirky_pozic)
        if nejsirsi <= sirka_obsahu + 0.01:
            break
        scale = max(scale * (sirka_obsahu / nejsirsi), TECHNICKY_MIN_SCALE)
    return scale


def _radky_s_metadaty(vsechny_sekce):
    """Zploští VŠECHNY řádky dokumentu (napříč sekcemi) do jednoho seznamu
    polozek s metadaty potřebnými pro vykreslení a stránkování — pořadí
    je zachované, takže řádky jedné sekce zůstávají pohromadě.

    Sekce BEZ řádků (`radky: []`, viz schéma) dostane jednu položku typu
    "nadpis" místo běžných položek typu "radek" — nese jen `sekce`, žádný
    `radek`/`od_g`/`do_g` (není co kreslit do mřížky ani co by repetice
    mohla indexovat). Je triviálně "první i poslední řádek" své sekce,
    takže dostane mezeru před i po jako normální osamocený řádek sekce."""
    polozky = []
    for sekce in vsechny_sekce:
        if not sekce["radky"]:
            polozky.append(
                {
                    "typ": "nadpis",
                    "sekce": sekce,
                    "je_prvni_v_sekci": True,
                    "je_posledni_v_sekci": True,
                }
            )
            continue
        globalni_takt_idx = 0
        pocet_radku_sekce = len(sekce["radky"])
        for i_radek, radek in enumerate(sekce["radky"]):
            pocet_taktu = len(radek["takty"])
            polozky.append(
                {
                    "typ": "radek",
                    "radek": radek,
                    "sekce": sekce,
                    "je_prvni_v_sekci": i_radek == 0,
                    "je_posledni_v_sekci": i_radek == pocet_radku_sekce - 1,
                    "od_g": globalni_takt_idx,
                    "do_g": globalni_takt_idx + pocet_taktu,
                }
            )
            globalni_takt_idx += pocet_taktu
    return polozky


def _ma_badge(radek):
    return any(t.get("takt") for t in radek["takty"])


def _volty_v_radku(sekce, od_g, do_g):
    """Volty sekce, které ZASAHUJÍ do rozsahu taktů [od_g, do_g) tohoto
    řádku — může jich být v jednom řádku i víc. Stejný způsob ořezání
    jako u repetice ve vygeneruj_pdf (seg_od/seg_do), jen tady stačí
    vědět JESTLI řádek zasahují, ne přesný rozsah (ten si spočte
    volající, co barvu/x-pozice skutečně kreslí)."""
    vysledek = []
    for volta in sekce.get("volty", []):
        seg_od = max(volta["od_taktu"], od_g)
        seg_do = min(volta["do_taktu"], do_g - 1)
        if seg_od <= seg_do:
            vysledek.append(volta)
    return vysledek


def _ma_navic_nad_radkem(polozka):
    """Potřebuje řádek REZERVOVANOU MEZERU navíc nad sebou (MEZERA_PRO_BADGE) —
    buď kvůli badge vlastního taktu, nebo kvůli hranaté závorce volty
    (zadání: "nad řádky s voltou zvětši mezeru, jako u označení
    vlastního taktu" — VĚDOMĚ stejný mechanismus, ne dva samostatné)."""
    if polozka["typ"] != "radek":
        return False
    radek = polozka["radek"]
    return _ma_badge(radek) or bool(_volty_v_radku(polozka["sekce"], polozka["od_g"], polozka["do_g"]))


def _vyska_obsahu_stranky(polozky_stranky, scale):
    """Součet výšek všech položek (+ mezer mezi nimi + rezervy pro badge/
    voltu) stránky PŘI daném `scale` — pro rozhodnutí, jestli se
    `polozky_stranky` ještě vejdou na výšku. Položka typu "nadpis"
    (sekce bez řádků, viz _radky_s_metadaty) nemá badge/voltu a bere
    stejnou výšku jako běžný řádek — jen se do ní nekreslí mřížka, viz
    vygeneruj_pdf."""
    vyska_radku = VYSKA_RADKU * scale
    mezera_stejna_sekce = MEZERA_RADKU_STEJNA_SEKCE * scale
    mezera_mezi_sekcemi = MEZERA_MEZI_SEKCEMI * scale
    mezera_pro_badge = MEZERA_PRO_BADGE * scale
    celkem = 0.0
    for polozka in polozky_stranky:
        if _ma_navic_nad_radkem(polozka):
            celkem += mezera_pro_badge
        celkem += vyska_radku
        celkem += (
            mezera_stejna_sekce if not polozka["je_posledni_v_sekci"] else mezera_mezi_sekcemi
        )
    return celkem


def _seskup_pro_zalomeni(polozky):
    """Seskupí položky tak, aby "nadpis" (sekce bez řádků) nikdy nezůstal
    sám na konci stránky, oddělený zalomením od obsahu, co po něm hned
    následuje — stránkuje se pak po CELÝCH skupinách (viz _rozvrhni_stranky),
    ne po jednotlivých položkách. Řetěz víc "nadpisů" za sebou (víc
    prázdných sekcí vedle sebe) se slepí dohromady s první SKUTEČNOU
    položkou, co po nich přijde — jinak by mohl zůstat osamocený i
    prostřední z nich. Nadpis úplně na konci dokumentu (nic už za ním
    není) zůstane sám — nemá s čím se slepit, a "osamocený na konci
    stránky" u posledního obsahu dokumentu není problém řešený tímhle
    zadáním (viz modul docstring)."""
    skupiny = []
    i = 0
    n = len(polozky)
    while i < n:
        skupina = [polozky[i]]
        i += 1
        while skupina[-1]["typ"] == "nadpis" and i < n:
            skupina.append(polozky[i])
            i += 1
        skupiny.append(skupina)
    return skupiny


def _rozvrhni_stranky(polozky, scale):
    """Rozdělí řádky na stránky JEN podle výšky — scale je teď společný
    pro celý dokument (viz modul docstring), takže se tu (na rozdíl od
    dřívější verze) neřeší nic jiného než kolik řádků se při něm vejde
    nad sebe na jednu stránku. Dělí se po SKUPINÁCH (_seskup_pro_zalomeni),
    ne po jednotlivých položkách, aby osamocený "nadpis" sekce bez řádků
    nezůstal na konci stránky odtržený od obsahu za ním."""
    vyska_dostupna = Y_ZACATEK_OBSAHU - OKRAJ
    stranky = []
    aktualni = []
    for skupina in _seskup_pro_zalomeni(polozky):
        kandidat = aktualni + skupina
        vyska = _vyska_obsahu_stranky(kandidat, scale)
        if aktualni and vyska > vyska_dostupna:
            stranky.append(aktualni)
            aktualni = skupina
        else:
            aktualni = kandidat
    if aktualni:
        stranky.append(aktualni)
    return stranky


def vygeneruj_pdf(pisen, akordy):
    """`pisen` — instance Pisen (název, interpret). `akordy` — JSON prošlý
    přes AkordovyZapisSerializer (schéma 2). Vrací bytes hotového PDF."""
    _zaregistruj_fonty()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(SIRKA_STRANKY, VYSKA_STRANKY))

    takt_vychozi = akordy["takt"]
    dob_vychozi = takt_vychozi["dob"]
    hodnota_vychozi = takt_vychozi["hodnota"]
    tempo = akordy.get("tempo")
    vsechny_sekce = akordy["sekce"]

    sirka_obsahu = SIRKA_STRANKY - 2 * OKRAJ - SIRKA_GUTTERU
    x0 = OKRAJ + SIRKA_GUTTERU

    def kresli_hlavicku():
        # Hlavička se NEŠKÁLUJE.
        y_baseline = VYSKA_STRANKY - OKRAJ - 28
        c.setFont(FONT_POPISEK_TUCNE, VELIKOST_TITULKU)
        c.setFillColorRGB(*BARVA_CERNA)
        c.drawString(OKRAJ, y_baseline, pisen.nazev.upper())
        if pisen.interpret:
            x_interpret = OKRAJ + pdfmetrics.stringWidth(
                pisen.nazev.upper(), FONT_POPISEK_TUCNE, VELIKOST_TITULKU
            )
            c.setFont(FONT_POPISEK, VELIKOST_INTERPRETA)
            c.setFillColorRGB(*BARVA_SEDA)
            c.drawString(x_interpret + 10, y_baseline, pisen.interpret)

        c.setFont(FONT_POPISEK, VELIKOST_INTERPRETA)
        c.setFillColorRGB(*BARVA_SEDA)
        text_taktu = f"{dob_vychozi}/{hodnota_vychozi}"
        if tempo:
            text_taktu = f"♩ = {tempo}   ·   {text_taktu}"
        c.drawRightString(SIRKA_STRANKY - OKRAJ, y_baseline, text_taktu)

        y_pravitko = y_baseline - 12
        c.setStrokeColorRGB(*BARVA_CERNA)
        c.setLineWidth(TLOUSTKA_PRAVITKA)
        c.line(OKRAJ, y_pravitko, SIRKA_STRANKY - OKRAJ, y_pravitko)
        return VYSKA_STRANKY - OKRAJ - 95

    polozky = _radky_s_metadaty(vsechny_sekce)

    if not polozky:
        kresli_hlavicku()
        c.showPage()
        c.save()
        return buffer.getvalue()

    # Mřížka (scale i šířky pozic) je SPOLEČNÁ pro CELÝ dokument, ne jen
    # jednu stránku (viz modul docstring) — počítá se tu JEDNOU, mimo
    # smyčku přes stránky, a použije se beze změny na každé z nich.
    # Položky typu "nadpis" (sekce bez řádků) do mřížky nepřispívají —
    # nemají žádné buňky.
    polozky_radek = [p for p in polozky if p["typ"] == "radek"]
    radky_dokumentu = [p["radek"] for p in polozky_radek]
    scale = _najdi_scale(polozky_radek, sirka_obsahu, dob_vychozi)
    sirka_doby_zakladni = (sirka_obsahu / (POCET_TAKTU_NA_RADEK * dob_vychozi)) * scale
    velikost_akordu = max(VELIKOST_AKORDU * scale, TECHNICKY_MIN_VELIKOST)
    velikost_sekce = max(VELIKOST_SEKCE * scale, TECHNICKY_MIN_VELIKOST)
    velikost_repetice_n = max(VELIKOST_REPETICE_N * scale, TECHNICKY_MIN_VELIKOST)
    velikost_badge = max(VELIKOST_BADGE_TAKTU * scale, TECHNICKY_MIN_VELIKOST)
    velikost_volta_cislo = max(VELIKOST_VOLTA_CISLO * scale, TECHNICKY_MIN_VELIKOST)
    vyska_radku = VYSKA_RADKU * scale
    mezera_stejna_sekce = MEZERA_RADKU_STEJNA_SEKCE * scale
    mezera_mezi_sekcemi = MEZERA_MEZI_SEKCEMI * scale
    mezera_pro_badge = MEZERA_PRO_BADGE * scale
    chord_offset = CHORD_BASELINE_OFFSET * scale
    sekce_offset = SEKCE_BASELINE_OFFSET * scale
    badge_nad_radkem = BADGE_NAD_RADKEM_OFFSET * scale
    volta_cara_offset = VOLTA_CARA_NAD_RADKEM_OFFSET * scale
    volta_noha = VYSKA_VOLTA_NOHY * scale
    sirky_pozic = _sirky_pozic(radky_dokumentu, sirka_doby_zakladni, velikost_akordu)
    mezery_vlevo, mezery_vpravo = _mezery_znacek_repetice(polozky_radek, velikost_repetice_n)
    sirky_pozic = _rozsir_sirky_pro_znacky(sirky_pozic, mezery_vlevo, mezery_vpravo)

    for polozky_stranky in _rozvrhni_stranky(polozky, scale):
        y = kresli_hlavicku()

        for polozka in polozky_stranky:
            sekce = polozka["sekce"]

            if polozka["typ"] == "nadpis":
                # Sekce bez řádků: jen nadpis na vlastním řádku, stejný
                # styl jako nadpis normální sekce (viz níž) — žádná
                # mřížka, žádné takty, žádné repetice (schéma repetice na
                # sekci bez taktů nepřipouští).
                y_radku = y
                if sekce.get("nazev"):
                    nazev_velky = sekce["nazev"].upper()
                    velikost_nazvu = _velikost_pro_text(
                        nazev_velky,
                        FONT_POPISEK_TUCNE,
                        SIRKA_GUTTERU - 6,
                        velikost_sekce,
                        TECHNICKY_MIN_VELIKOST,
                    )
                    c.setFont(FONT_POPISEK_TUCNE, velikost_nazvu)
                    c.setFillColorRGB(*BARVA_SEDA)
                    c.drawString(OKRAJ, y_radku - sekce_offset, nazev_velky)

                y -= vyska_radku + (
                    mezera_stejna_sekce if not polozka["je_posledni_v_sekci"] else mezera_mezi_sekcemi
                )
                continue

            radek = polozka["radek"]
            od_g, do_g = polozka["od_g"], polozka["do_g"]
            volty_radku = _volty_v_radku(sekce, od_g, do_g)

            navic_pred_radkem = mezera_pro_badge if (_ma_badge(radek) or volty_radku) else 0
            y -= navic_pred_radkem
            y_radku = y

            if polozka["je_prvni_v_sekci"] and sekce.get("nazev"):
                nazev_velky = sekce["nazev"].upper()
                velikost_nazvu = _velikost_pro_text(
                    nazev_velky,
                    FONT_POPISEK_TUCNE,
                    SIRKA_GUTTERU - 6,
                    velikost_sekce,
                    TECHNICKY_MIN_VELIKOST,
                )
                c.setFont(FONT_POPISEK_TUCNE, velikost_nazvu)
                c.setFillColorRGB(*BARVA_SEDA)
                c.drawString(OKRAJ, y_radku - sekce_offset, nazev_velky)

            # --- takty a buňky ---
            c.setStrokeColorRGB(*BARVA_CERNA)
            c.setLineWidth(TLOUSTKA_CARY)
            x = x0
            c.line(x, y_radku - vyska_radku, x, y_radku)
            pozice = 0
            for takt_v_radku in radek["takty"]:
                efektivni = _efektivni_takt(takt_v_radku, takt_vychozi)
                bunky = takt_v_radku["bunky"]
                sirky_dob = sirky_pozic[pozice : pozice + len(bunky)]
                sirka_taktu = sum(sirky_dob)

                if takt_v_radku.get("takt"):
                    c.setFont(FONT_POPISEK, velikost_badge)
                    c.setFillColorRGB(*BARVA_SEDA)
                    c.drawString(
                        x + 2,
                        y_radku + badge_nad_radkem,
                        f"{efektivni['dob']}/{efektivni['hodnota']}",
                    )

                x_doba = x
                for i_doba, (text, sirka_teto_doby) in enumerate(zip(bunky, sirky_dob)):
                    # Pozice s rezervou pro značku repetice (viz
                    # _mezery_znacek_repetice) nesmí akord/tečku centrovat
                    # do CELÉ (rozšířené) šířky — to by posunulo obsah
                    # do prostoru značky. Centruje se jen v PŮVODNÍ
                    # ("přirozené") šířce, rezerva zůstává čistá na svojí
                    # straně (vlevo pro začátek repetice, vpravo pro konec).
                    p_abs = pozice + i_doba
                    posun_vlevo = mezery_vlevo.get(p_abs, 0.0)
                    posun_vpravo = mezery_vpravo.get(p_abs, 0.0)
                    prirozena_sirka = sirka_teto_doby - posun_vlevo - posun_vpravo
                    x_stred = x_doba + posun_vlevo + prirozena_sirka / 2
                    if text:
                        c.setFont(FONT_AKORD, velikost_akordu)
                        c.setFillColorRGB(*BARVA_CERNA)
                        c.drawCentredString(x_stred, y_radku - chord_offset, text)
                    else:
                        # Tečka VŽDY — žádné potlačování (viz zadání bod 4).
                        # Díky rozšiřování dob (bod 5) do ní teď nemá jak
                        # zasáhnout přetékající akord odjinud.
                        c.setFillColorRGB(*BARVA_SEDA)
                        c.circle(
                            x_stred,
                            y_radku - chord_offset + velikost_akordu * 0.32,
                            max(1.6 * scale, 0.6),
                            stroke=0,
                            fill=1,
                        )
                    x_doba += sirka_teto_doby

                x += sirka_taktu
                pozice += len(bunky)
                c.line(x, y_radku - vyska_radku, x, y_radku)

            # --- repetice sekce, které zasahují do TOHOTO řádku ---
            for rep in sekce.get("repetice", []):
                seg_od = max(rep["od_taktu"], od_g)
                seg_do = min(rep["do_taktu"], do_g - 1)
                if seg_od > seg_do:
                    continue
                kresli_konec = rep["do_taktu"] < do_g
                mezera_konce = 0.0
                if kresli_konec:
                    do_v_radku = seg_do - od_g
                    p_konec = (
                        _pozice_zacatku_taktu(radek, do_v_radku)
                        + len(radek["takty"][do_v_radku]["bunky"])
                        - 1
                    )
                    mezera_konce = mezery_vpravo.get(p_konec, 0.0)
                _kresli_repetici(
                    c,
                    x0=x0,
                    y_radku=y_radku,
                    vyska_radku=vyska_radku,
                    sirky_pozic=sirky_pozic,
                    radek=radek,
                    od_v_radku=seg_od - od_g,
                    do_v_radku=seg_do - od_g,
                    kresli_zacatek=rep["od_taktu"] >= od_g,
                    kresli_konec=kresli_konec,
                    krat=rep["krat"],
                    velikost_repetice_n=velikost_repetice_n,
                    chord_offset=chord_offset,
                    mezera_konce=mezera_konce,
                )

            # --- volty, které zasahují do TOHOTO řádku ---
            for volta in volty_radku:
                seg_od = max(volta["od_taktu"], od_g)
                seg_do = min(volta["do_taktu"], do_g - 1)
                volta_od_v_radku = seg_od - od_g
                volta_do_v_radku = seg_do - od_g
                # Volta smí (stejně jako repetice) přes víc řádků JEDNÉ
                # sekce — kresli_zacatek/kresli_konec (stejný vzor jako u
                # _kresli_repetici) řeší, jestli SKUTEČNÝ začátek/konec
                # volty padne zrovna do TOHOTO řádku, nebo jestli je to
                # jen pokračování/předěl přes zalomení řádku (tam se noha
                # závorky nekreslí, jen vodorovná čára pokračuje dál).
                kresli_zacatek = volta["od_taktu"] >= od_g
                kresli_konec = volta["do_taktu"] < do_g
                # Volta se může na svém začátku/konci potkat se sdílenou
                # pozicí, co má REZERVU pro značku repetice (viz
                # _mezery_znacek_repetice) — když volta končí přesně tam,
                # kde končí i repetice (běžný případ, viz zadání), musí
                # závorka skončit PŘED rezervou pro '×N', ne za ní (jinak
                # by vyjela až za konec repetice/přes okraj stránky).
                # Platí to jen tam, kde se skutečně kreslí odpovídající
                # konec — na pokračovací řádek by se rezerva odjinud
                # nesouvisejícím způsobem promítla do vodorovné čáry.
                posun_zacatku = 0.0
                if kresli_zacatek:
                    p_zacatek_volty = _pozice_zacatku_taktu(radek, volta_od_v_radku)
                    posun_zacatku = mezery_vlevo.get(p_zacatek_volty, 0.0)
                posun_konce = 0.0
                if kresli_konec:
                    p_konec_volty = (
                        _pozice_zacatku_taktu(radek, volta_do_v_radku)
                        + len(radek["takty"][volta_do_v_radku]["bunky"])
                        - 1
                    )
                    posun_konce = mezery_vpravo.get(p_konec_volty, 0.0)
                _kresli_voltu(
                    c,
                    x0=x0,
                    y_radku=y_radku,
                    sirky_pozic=sirky_pozic,
                    radek=radek,
                    od_v_radku=volta_od_v_radku,
                    do_v_radku=volta_do_v_radku,
                    kresli_zacatek=kresli_zacatek,
                    kresli_konec=kresli_konec,
                    posun_zacatku=posun_zacatku,
                    posun_konce=posun_konce,
                    cislo=volta["cislo"],
                    velikost_cisla=velikost_volta_cislo,
                    volta_cara_offset=volta_cara_offset,
                    volta_noha=volta_noha,
                )

            y -= vyska_radku + (
                mezera_stejna_sekce if not polozka["je_posledni_v_sekci"] else mezera_mezi_sekcemi
            )

        c.showPage()

    c.save()
    return buffer.getvalue()


def _x_pozice_taktu(radek, sirky_pozic, index_taktu):
    """X offset (od začátku řádku) taktu na daném indexu — sečte SDÍLENÉ
    šířky pozic (viz _sirky_pozic) všech předchozích taktů TOHOTO řádku."""
    pozice_zacatku = _pozice_zacatku_taktu(radek, index_taktu)
    return sum(sirky_pozic[:pozice_zacatku])


def _kresli_repetici(
    c,
    x0,
    y_radku,
    vyska_radku,
    sirky_pozic,
    radek,
    od_v_radku,
    do_v_radku,
    kresli_zacatek,
    kresli_konec,
    krat,
    velikost_repetice_n,
    chord_offset,
    mezera_konce,
):
    """Tlustá čára + dvě tečky na začátku a konci rozsahu, ×N vpravo od
    konce. Rozsah je už OŘÍZNUTÝ na tenhle řádek (viz volající).

    Začátek (`x_zacatek`) se kreslí přesně na hranici taktu — rezerva
    pro `|:` (SIRKA_ZNACKY_ZACATEK_REPETICE) žije UVNITŘ šířky prvního
    taktu repetice (viz _mezery_znacek_repetice), takže samotná čára a
    tečky (na fixním `+4.5` odstupu) do ní spadnou samy, aniž by se
    tahle funkce musela starat o posun — akord/tečku v té buňce posouvá
    z cesty hlavní kreslicí smyčka (viz vygeneruj_pdf).

    Konec je JINAK: `×N` text má proměnlivou šířku (`krat` 2-16), a
    "svoje" místo je REZERVOVANÉ ZA hranicí posledního taktu repetice
    (`mezera_konce`, viz _mezery_znacek_repetice) — proto se `x_konec`
    (kam se kreslí čára/tečky/text) odsune o `mezera_konce` DOVNITŘ
    (doleva) od skutečné (rozšířené) hranice taktu, aby text skončil
    přesně na ní, ne za ní."""
    x_zacatek = x0 + _x_pozice_taktu(radek, sirky_pozic, od_v_radku)
    x_konec_hranice = x0 + _x_pozice_taktu(radek, sirky_pozic, do_v_radku + 1)
    x_konec = x_konec_hranice - mezera_konce
    y_tecka_horni = y_radku - vyska_radku * 0.35
    y_tecka_dolni = y_radku - vyska_radku * 0.65

    c.setStrokeColorRGB(*BARVA_CERNA)
    c.setLineWidth(TLOUSTKA_REPETICE)
    c.setFillColorRGB(*BARVA_CERNA)

    if kresli_zacatek:
        c.line(x_zacatek, y_radku - vyska_radku, x_zacatek, y_radku)
        c.circle(x_zacatek + 4.5, y_tecka_horni, 1.6, stroke=0, fill=1)
        c.circle(x_zacatek + 4.5, y_tecka_dolni, 1.6, stroke=0, fill=1)

    if kresli_konec:
        c.line(x_konec, y_radku - vyska_radku, x_konec, y_radku)
        c.circle(x_konec - 4.5, y_tecka_horni, 1.6, stroke=0, fill=1)
        c.circle(x_konec - 4.5, y_tecka_dolni, 1.6, stroke=0, fill=1)
        c.setFont(FONT_POPISEK_TUCNE, velikost_repetice_n)
        c.drawString(x_konec + ODSTUP_ZNACKY_KONCE_OD_CARY, y_radku - chord_offset, f"×{krat}")


def _kresli_voltu(
    c,
    x0,
    y_radku,
    sirky_pozic,
    radek,
    od_v_radku,
    do_v_radku,
    kresli_zacatek,
    kresli_konec,
    posun_zacatku,
    posun_konce,
    cislo,
    velikost_cisla,
    volta_cara_offset,
    volta_noha,
):
    """Hranatá závorka nad takty volty — vodorovná čára v rezervované
    mezeře nad řádkem (viz _ma_navic_nad_radkem), svislá "noha" VLEVO
    jen když SKUTEČNÝ začátek volty padne do tohoto řádku, VPRAVO jen
    tehdy A NAVÍC jen když volta NENÍ číslo 1. Zadání: "otevřená vpravo
    u volty 1, zavřená u poslední" — u dvojice prima/secunda je "volta
    1" a "poslední volta" vždycky přesně tahle dvě čísla (1 a 2), takže
    pravidlo zobecňujeme na STANDARDNÍ notační konvenci pro 3./4. konec:
    číslo 1 je vždycky otevřené (spoléhá na sousední konec repetice),
    KAŽDÉ DALŠÍ číslo (2, 3, 4) je uzavřené ze všech stran — ne jen to
    nejvyšší. Rozsah je už OŘÍZNUTÝ na tenhle řádek (viz volající) —
    `kresli_zacatek`/`kresli_konec` (stejný vzor jako _kresli_repetici)
    řeší volty PŘES VÍC ŘÁDKŮ jedné sekce (schéma to dovoluje stejně
    jako u repetice): na řádku, kde volta jen POKRAČUJE (nezačíná ani
    nekončí tam), se kreslí jen vodorovná čára, bez nohy a bez čísla.

    `posun_zacatku`/`posun_konce` (viz volající, jen když se odpovídající
    konec skutečně kreslí) odsunou závorku DOVNITŘ, když se potká se
    sdílenou pozicí, co má rezervu pro značku repetice
    (_mezery_znacek_repetice) — jinak by závorka končila/začínala AŽ ZA
    touhle rezervou, ne na hranici taktu."""
    x_zacatek = x0 + _x_pozice_taktu(radek, sirky_pozic, od_v_radku) + posun_zacatku
    x_konec = x0 + _x_pozice_taktu(radek, sirky_pozic, do_v_radku + 1) - posun_konce
    y_cara = y_radku + volta_cara_offset
    y_noha_dolu = y_cara - volta_noha

    c.setStrokeColorRGB(*BARVA_CERNA)
    c.setLineWidth(TLOUSTKA_VOLTY)
    if kresli_zacatek:
        c.line(x_zacatek, y_noha_dolu, x_zacatek, y_cara)
    c.line(x_zacatek, y_cara, x_konec, y_cara)
    if kresli_konec and cislo != 1:
        c.line(x_konec, y_noha_dolu, x_konec, y_cara)

    if kresli_zacatek:
        c.setFont(FONT_POPISEK_TUCNE, velikost_cisla)
        c.setFillColorRGB(*BARVA_CERNA)
        c.drawString(x_zacatek + 2, y_cara + 1, f"{cislo}.")
