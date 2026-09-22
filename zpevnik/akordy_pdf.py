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

Šířka doby je jednotná PRO NEROZŠÍŘENÉ doby v celém dokumentu (takty bez
dlouhých akordů jsou tak pod sebou zarovnané) — ale KAŽDÁ doba se
individuálně rozšíří, pokud se do základní šířky nevejde její akord
(žádné lokální zmenšování písma, žádné přetékání do sousední doby). Když
tím některý řádek přesáhne šířku stránky, zmenší se ŠÍŘKA DOBY (a s ní
úměrně velikost písma) pro CELÝ DOKUMENT, dokud se nejširší řádek nevejde
— hledá se iterativně, protože širší doba × menší písmo jsou provázané.
"""

import io
import os

from reportlab.lib.pagesizes import A4
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


# --- rozměry (body, A4 = 595 x 842) — kalibrováno na referenční
# africa_chord_chart.pdf, viz commit historie ---
SIRKA_STRANKY, VYSKA_STRANKY = A4
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
    """Šířka JEDNÉ doby — základní, POKUD se do ní vejde akord (prázdná
    doba se nikdy nerozšiřuje, jen nese tečku). Jinak přesně tak široká,
    aby akord i s rezervou sedl celý (viz zadání bod 5: akord nesmí
    zasahovat do sousední doby, žádné přetékání)."""
    if not text:
        return sirka_doby_zakladni
    potrebna = pdfmetrics.stringWidth(text, FONT_AKORD, velikost_akordu) + REZERVA_MEZI_AKORDY
    return max(sirka_doby_zakladni, potrebna)


def _sirky_dob_v_taktu(bunky, sirka_doby_zakladni, velikost_akordu):
    return [_sirka_doby(b, sirka_doby_zakladni, velikost_akordu) for b in bunky]


def _sirka_taktu(takt_v_radku, sirka_doby_zakladni, velikost_akordu):
    return sum(_sirky_dob_v_taktu(takt_v_radku["bunky"], sirka_doby_zakladni, velikost_akordu))


def _sirka_radku(radek, sirka_doby_zakladni, velikost_akordu):
    return sum(_sirka_taktu(t, sirka_doby_zakladni, velikost_akordu) for t in radek["takty"])


def _najdi_scale(vsechny_sekce, sirka_obsahu, dob_vychozi):
    """Iterativně najde největší `scale` (<=1), při kterém se nejširší
    řádek (počítaný SE VŠEMI rozšířeními dob, viz _sirka_radku) vejde do
    šířky stránky. Rozšíření dob závisí na velikosti písma, ta na scale —
    proto iterace, ne jeden výpočet (viz modul docstring)."""
    radky = [radek for sekce in vsechny_sekce for radek in sekce["radky"]]
    if not radky:
        return 1.0

    zakladni_sirka_doby_pri_1 = sirka_obsahu / (POCET_TAKTU_NA_RADEK * dob_vychozi)
    scale = 1.0
    for _ in range(40):
        sirka_doby_zakladni = zakladni_sirka_doby_pri_1 * scale
        velikost_akordu = max(VELIKOST_AKORDU * scale, TECHNICKY_MIN_VELIKOST)
        nejsirsi = max(_sirka_radku(r, sirka_doby_zakladni, velikost_akordu) for r in radky)
        if nejsirsi <= sirka_obsahu + 0.01:
            break
        scale = max(scale * (sirka_obsahu / nejsirsi), TECHNICKY_MIN_SCALE)
    return scale


def vygeneruj_pdf(pisen, akordy):
    """`pisen` — instance Pisen (název, interpret). `akordy` — JSON prošlý
    přes AkordovyZapisSerializer (schéma 2). Vrací bytes hotového PDF."""
    _zaregistruj_fonty()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    takt_vychozi = akordy["takt"]
    dob_vychozi = takt_vychozi["dob"]
    hodnota_vychozi = takt_vychozi["hodnota"]
    tempo = akordy.get("tempo")
    vsechny_sekce = akordy["sekce"]

    sirka_obsahu = SIRKA_STRANKY - 2 * OKRAJ - SIRKA_GUTTERU
    x0 = OKRAJ + SIRKA_GUTTERU

    scale = _najdi_scale(vsechny_sekce, sirka_obsahu, dob_vychozi)
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

    dolni_limit = OKRAJ + vyska_radku

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

    def nova_stranka():
        c.showPage()
        return kresli_hlavicku()

    y = kresli_hlavicku()

    if not vsechny_sekce:
        c.showPage()
        c.save()
        return buffer.getvalue()

    for i_sekce, sekce in enumerate(vsechny_sekce):
        # Globální index taktu V RÁMCI SEKCE — repetice na sekci indexují
        # přes všechny její řádky, ne jen jeden.
        globalni_takt_idx = 0
        radky_s_rozsahy = []
        for radek in sekce["radky"]:
            pocet_taktu = len(radek["takty"])
            radky_s_rozsahy.append((radek, globalni_takt_idx, globalni_takt_idx + pocet_taktu))
            globalni_takt_idx += pocet_taktu

        for i_radek, (radek, od_g, do_g) in enumerate(radky_s_rozsahy):
            ma_badge = any(t.get("takt") for t in radek["takty"])
            navic_pred_radkem = mezera_pro_badge if ma_badge else 0

            if y - navic_pred_radkem - vyska_radku < dolni_limit:
                y = nova_stranka()
            y -= navic_pred_radkem
            y_radku = y

            if i_radek == 0 and sekce.get("nazev"):
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
            for takt_v_radku in radek["takty"]:
                efektivni = _efektivni_takt(takt_v_radku, takt_vychozi)
                bunky = takt_v_radku["bunky"]
                sirky_dob = _sirky_dob_v_taktu(bunky, sirka_doby_zakladni, velikost_akordu)
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
                    sirka_doby_zakladni=sirka_doby_zakladni,
                    velikost_akordu=velikost_akordu,
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
                mezera_stejna_sekce if i_radek < len(radky_s_rozsahy) - 1 else mezera_mezi_sekcemi
            )

    c.showPage()
    c.save()
    return buffer.getvalue()


def _x_pozice_taktu(radek, sirka_doby_zakladni, velikost_akordu, index_taktu):
    """X offset (od začátku řádku) taktu na daném indexu — sečte SKUTEČNÉ
    (případně rozšířené) šířky všech předchozích taktů."""
    x = 0
    for t in radek["takty"][:index_taktu]:
        x += _sirka_taktu(t, sirka_doby_zakladni, velikost_akordu)
    return x


def _kresli_repetici(
    c,
    x0,
    y_radku,
    vyska_radku,
    sirka_doby_zakladni,
    velikost_akordu,
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
    x_zacatek = x0 + _x_pozice_taktu(radek, sirka_doby_zakladni, velikost_akordu, od_v_radku)
    x_konec = x0 + _x_pozice_taktu(radek, sirka_doby_zakladni, velikost_akordu, do_v_radku + 1)
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
