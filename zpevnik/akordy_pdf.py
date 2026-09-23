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
MEZERA_MEZI_SEKCEMI = 11  # mezi poslední řádkou jedné sekce a první další
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


def _najdi_scale(radky, sirka_obsahu, dob_vychozi):
    """Iterativně najde největší `scale` (<=1), při kterém se nejširší
    řádek MEZI `radky` (počítaný přes sdílené šířky pozic, viz
    _sirky_pozic) vejde do šířky stránky. Rozšíření dob závisí na
    velikosti písma, ta na scale — proto iterace, ne jeden výpočet.

    Nejširší řádek = řádek s NEJVÍC pozicemi: šířky pozic jsou max přes
    `radky`, takže součet za víc pozic je vždycky >= součet za míň pozic
    (všechny členy jsou kladné) — stačí sečíst CELÉ pole `_sirky_pozic`
    (délka = nejdelší řádek), není potřeba porovnávat řádek po řádku."""
    if not radky:
        return 1.0

    zakladni_sirka_doby_pri_1 = sirka_obsahu / (POCET_TAKTU_NA_RADEK * dob_vychozi)
    scale = 1.0
    for _ in range(40):
        sirka_doby_zakladni = zakladni_sirka_doby_pri_1 * scale
        velikost_akordu = max(VELIKOST_AKORDU * scale, TECHNICKY_MIN_VELIKOST)
        sirky_pozic = _sirky_pozic(radky, sirka_doby_zakladni, velikost_akordu)
        nejsirsi = sum(sirky_pozic)
        if nejsirsi <= sirka_obsahu + 0.01:
            break
        scale = max(scale * (sirka_obsahu / nejsirsi), TECHNICKY_MIN_SCALE)
    return scale


def _radky_s_metadaty(vsechny_sekce):
    """Zploští VŠECHNY řádky dokumentu (napříč sekcemi) do jednoho seznamu
    polozek s metadaty potřebnými pro vykreslení a stránkování — pořadí
    je zachované, takže řádky jedné sekce zůstávají pohromadě."""
    polozky = []
    for sekce in vsechny_sekce:
        globalni_takt_idx = 0
        pocet_radku_sekce = len(sekce["radky"])
        for i_radek, radek in enumerate(sekce["radky"]):
            pocet_taktu = len(radek["takty"])
            polozky.append(
                {
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


def _vyska_obsahu_stranky(polozky_stranky, scale):
    """Součet výšek všech řádků (+ mezer mezi nimi + rezervy pro badge)
    stránky PŘI daném `scale` — pro rozhodnutí, jestli se `polozky_stranky`
    ještě vejdou na výšku."""
    vyska_radku = VYSKA_RADKU * scale
    mezera_stejna_sekce = MEZERA_RADKU_STEJNA_SEKCE * scale
    mezera_mezi_sekcemi = MEZERA_MEZI_SEKCEMI * scale
    mezera_pro_badge = MEZERA_PRO_BADGE * scale
    celkem = 0.0
    for polozka in polozky_stranky:
        if _ma_badge(polozka["radek"]):
            celkem += mezera_pro_badge
        celkem += vyska_radku
        celkem += (
            mezera_stejna_sekce if not polozka["je_posledni_v_sekci"] else mezera_mezi_sekcemi
        )
    return celkem


def _rozvrhni_stranky(polozky, scale):
    """Rozdělí řádky na stránky JEN podle výšky — scale je teď společný
    pro celý dokument (viz modul docstring), takže se tu (na rozdíl od
    dřívější verze) neřeší nic jiného než kolik řádků se při něm vejde
    nad sebe na jednu stránku."""
    vyska_dostupna = Y_ZACATEK_OBSAHU - OKRAJ
    stranky = []
    aktualni = []
    for polozka in polozky:
        kandidat = aktualni + [polozka]
        vyska = _vyska_obsahu_stranky(kandidat, scale)
        if aktualni and vyska > vyska_dostupna:
            stranky.append(aktualni)
            aktualni = [polozka]
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
    radky_dokumentu = [p["radek"] for p in polozky]
    scale = _najdi_scale(radky_dokumentu, sirka_obsahu, dob_vychozi)
    sirka_doby_zakladni = (sirka_obsahu / (POCET_TAKTU_NA_RADEK * dob_vychozi)) * scale
    velikost_akordu = max(VELIKOST_AKORDU * scale, TECHNICKY_MIN_VELIKOST)
    velikost_sekce = max(VELIKOST_SEKCE * scale, TECHNICKY_MIN_VELIKOST)
    velikost_repetice_n = max(VELIKOST_REPETICE_N * scale, TECHNICKY_MIN_VELIKOST)
    velikost_badge = max(VELIKOST_BADGE_TAKTU * scale, TECHNICKY_MIN_VELIKOST)
    vyska_radku = VYSKA_RADKU * scale
    mezera_stejna_sekce = MEZERA_RADKU_STEJNA_SEKCE * scale
    mezera_mezi_sekcemi = MEZERA_MEZI_SEKCEMI * scale
    mezera_pro_badge = MEZERA_PRO_BADGE * scale
    chord_offset = CHORD_BASELINE_OFFSET * scale
    sekce_offset = SEKCE_BASELINE_OFFSET * scale
    badge_nad_radkem = BADGE_NAD_RADKEM_OFFSET * scale
    sirky_pozic = _sirky_pozic(radky_dokumentu, sirka_doby_zakladni, velikost_akordu)

    for polozky_stranky in _rozvrhni_stranky(polozky, scale):
        y = kresli_hlavicku()

        for polozka in polozky_stranky:
            radek = polozka["radek"]
            sekce = polozka["sekce"]
            od_g, do_g = polozka["od_g"], polozka["do_g"]

            navic_pred_radkem = mezera_pro_badge if _ma_badge(radek) else 0
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
                for text, sirka_teto_doby in zip(bunky, sirky_dob):
                    x_stred = x_doba + sirka_teto_doby / 2
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
                    kresli_konec=rep["do_taktu"] < do_g,
                    krat=rep["krat"],
                    velikost_repetice_n=velikost_repetice_n,
                    chord_offset=chord_offset,
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
):
    """Tlustá čára + dvě tečky na začátku a konci rozsahu, ×N vpravo od
    konce. Rozsah je už OŘÍZNUTÝ na tenhle řádek (viz volající)."""
    x_zacatek = x0 + _x_pozice_taktu(radek, sirky_pozic, od_v_radku)
    x_konec = x0 + _x_pozice_taktu(radek, sirky_pozic, do_v_radku + 1)
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
        c.drawString(x_konec + 8, y_radku - chord_offset, f"×{krat}")
