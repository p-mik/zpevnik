"""Generuje PDF akordového zápisu, schéma 2 (viz
PC_zpevnik_akordovy_zapis_upravy.md).

reportlab, NE weasyprint — ten by potřeboval systémové knihovny navíc v
Docker image. Fonty jsou přibalené v repu (zpevnik/fonts/, viz LICENSE.md
tam), žádné systémové — jinak by vzhled záležel na tom, co je zrovna
nainstalované na serveru.

Kreslí se přímo přes nízkoúrovňové Canvas API (ne platypus/flowables) —
mřížka akordů s ručním umisťováním potřebuje přesnou kontrolu pozic.

ŘÁDEK = ŘÁDEK. Appka sama nikdy nezalamuje — jak je řádek napsaný v
editoru, tak vyjde v PDF (viz zadání). Když se nejdelší řádek nevejde do
`POCET_TAKTU_NA_RADEK` (4) taktů výchozího taktu, zmenší se ŠÍŘKA DOBY
(a s ní úměrně všechno ostatní) pro CELÝ dokument, ne jen ten řádek.
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

VYSKA_RADKU = 28  # výška řádku PŘI scale=1 (žádné zalomení, viz nahoře)
MEZERA_RADKU_STEJNA_SEKCE = 4  # mezi dvěma řádky TÉŽE sekce
MEZERA_MEZI_SEKCEMI = 11  # mezi poslední řádkou jedné sekce a první další
CHORD_BASELINE_OFFSET = 19  # od horního okraje řádkového pásu
SEKCE_BASELINE_OFFSET = 18
BADGE_BASELINE_OFFSET = 7  # malé "2/4" u taktu s vlastním taktem — OD HORNÍHO okraje řádku dolů

VELIKOST_TITULKU = 26  # hlavička SE NEŠKÁLUJE (viz zadání: jen dobyk/akordy/sekce/mezery)
VELIKOST_INTERPRETA = 13
VELIKOST_SEKCE = 11
VELIKOST_AKORDU = 17.5
VELIKOST_REPETICE_N = 16
VELIKOST_BADGE_TAKTU = 7
# "Žádná spodní hranice velikosti písma" (viz zadání) — tohle NENÍ čitelnostní
# minimum, jen technická pojistka proti nulové/záporné velikosti při
# patologicky dlouhém řádku.
TECHNICKY_MIN_VELIKOST = 1

TLOUSTKA_CARY = 0.8
TLOUSTKA_REPETICE = 2.2
TLOUSTKA_PRAVITKA = 1.2

BARVA_SEDA = (0.3, 0.3, 0.3)
BARVA_CERNA = (0, 0, 0)

REZERVA_MEZI_AKORDY = 5


def _efektivni_takt(takt_v_radku, takt_vychozi):
    return takt_v_radku.get("takt") or takt_vychozi


def _delka_radku_v_dobach(radek, takt_vychozi):
    return sum(_efektivni_takt(t, takt_vychozi)["dob"] for t in radek["takty"])


def _pozice_v_taktu(bunky_taktu, sirka_doby, sirka_taktu):
    """Pro každou OBSAZENOU dobu v taktu vrátí (text, x_offset, dostupna_sirka).

    Dostupná šířka sahá až k DALŠÍ obsazené době, nebo ke konci taktu —
    mezi dobami není žádná čára, akord smí vizuálně přetéct do prázdných
    dob za sebou. Prázdné doby (pro tečku) se vrací zvlášť, viz volající."""
    obsazene = [i for i, text in enumerate(bunky_taktu) if text]
    vysledek = []
    for poradi, i in enumerate(obsazene):
        x_offset = i * sirka_doby
        pristi = obsazene[poradi + 1] * sirka_doby if poradi + 1 < len(obsazene) else sirka_taktu
        vysledek.append((bunky_taktu[i], i, x_offset, pristi - x_offset))
    return vysledek


def _velikost_pro_text(text, font, dostupna_sirka, zakladni_velikost, min_velikost):
    """Obecná verze _velikost_pro_bunku — zmenšuje libovolný text (label
    sekce, badge taktu), dokud se nevejde do dostupné šířky. Použito i pro
    název sekce v gutteru: krátké (INTRO, SLOKA) se nezmenší vůbec, dlouhé
    nebo volně psané ANO — gutter má pevnou šířku (SIRKA_GUTTERU)."""
    velikost = zakladni_velikost
    while velikost > min_velikost and pdfmetrics.stringWidth(text, font, velikost) > dostupna_sirka:
        velikost -= 0.5
    return max(velikost, min_velikost)


def _velikost_pro_bunku(text, dostupna_sirka, zakladni_velikost, min_velikost):
    """Jednotná velikost PRO CELÝ DOKUMENT (`zakladni_velikost`, už
    zahrnuje škálování na délku nejdelšího řádku), POKUD se text vejde do
    dostupné šířky — jinak se zmenšuje, dokud se nevejde (jen tahle buňka).
    `min_velikost` je čistě technická pojistka (viz TECHNICKY_MIN_VELIKOST),
    ne čitelnostní hranice — ta podle zadání neexistuje."""
    velikost = zakladni_velikost
    limit = dostupna_sirka - REZERVA_MEZI_AKORDY * (zakladni_velikost / VELIKOST_AKORDU)
    while velikost > min_velikost and pdfmetrics.stringWidth(text, FONT_AKORD, velikost) > limit:
        velikost -= 0.5
    return max(velikost, min_velikost)


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

    # --- škálování dokumentu: nejdelší řádek určuje šířku doby pro VŠECHNY ---
    nejdelsi_radek_v_dobach = 0
    for sekce in vsechny_sekce:
        for radek in sekce["radky"]:
            nejdelsi_radek_v_dobach = max(
                nejdelsi_radek_v_dobach, _delka_radku_v_dobach(radek, takt_vychozi)
            )
    cil_dob_na_radek = max(POCET_TAKTU_NA_RADEK * dob_vychozi, nejdelsi_radek_v_dobach)
    sirka_doby = sirka_obsahu / cil_dob_na_radek
    scale = (POCET_TAKTU_NA_RADEK * dob_vychozi) / cil_dob_na_radek  # <= 1

    velikost_akordu = max(VELIKOST_AKORDU * scale, TECHNICKY_MIN_VELIKOST)
    velikost_sekce = max(VELIKOST_SEKCE * scale, TECHNICKY_MIN_VELIKOST)
    velikost_repetice_n = max(VELIKOST_REPETICE_N * scale, TECHNICKY_MIN_VELIKOST)
    velikost_badge = max(VELIKOST_BADGE_TAKTU * scale, TECHNICKY_MIN_VELIKOST)
    vyska_radku = VYSKA_RADKU * scale
    mezera_stejna_sekce = MEZERA_RADKU_STEJNA_SEKCE * scale
    mezera_mezi_sekcemi = MEZERA_MEZI_SEKCEMI * scale
    chord_offset = CHORD_BASELINE_OFFSET * scale
    sekce_offset = SEKCE_BASELINE_OFFSET * scale
    badge_offset = BADGE_BASELINE_OFFSET * scale

    dolni_limit = OKRAJ + vyska_radku

    def kresli_hlavicku():
        # Hlavička se NEŠKÁLUJE (viz zadání: jen doby/akordy/sekce/mezery).
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
        # přes všechny její řádky (viz zadání), ne jen jeden.
        globalni_takt_idx = 0
        # (radek_idx, od_taktu_globalne, do_taktu_globalne_vyloucene, x_pozice_taktu[])
        radky_s_rozsahy = []
        for radek in sekce["radky"]:
            pocet_taktu = len(radek["takty"])
            radky_s_rozsahy.append((radek, globalni_takt_idx, globalni_takt_idx + pocet_taktu))
            globalni_takt_idx += pocet_taktu

        for i_radek, (radek, od_g, do_g) in enumerate(radky_s_rozsahy):
            if y - vyska_radku < dolni_limit:
                y = nova_stranka()
            y_radku = y

            if i_radek == 0 and sekce.get("nazev"):
                nazev_velky = sekce["nazev"].upper()
                # Gutter má pevnou šířku — dlouhý/volný název sekce (na
                # rozdíl od krátkých INTRO/SLOKA) se zmenší, ať nezasahuje
                # do prvního taktu (viz zadání: sekce je blok s vlastním
                # rámečkem, ne že by přetékala do not).
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
                dob_taktu = efektivni["dob"]
                sirka_taktu = dob_taktu * sirka_doby
                bunky = takt_v_radku["bunky"]

                if takt_v_radku.get("takt"):
                    c.setFont(FONT_POPISEK, velikost_badge)
                    c.setFillColorRGB(*BARVA_SEDA)
                    c.drawString(
                        x + 3, y_radku - badge_offset, f"{dob_taktu}/{efektivni['hodnota']}"
                    )

                obsazene_pozice = _pozice_v_taktu(bunky, sirka_doby, sirka_taktu)
                obsazene_indexy = {i for _, i, _, _ in obsazene_pozice}
                # akordy (a jejich SKUTEČNÁ vykreslená šířka, pro tečky níž)
                skutecne_konce = {}
                for text, idx_doby, x_offset, dostupna in obsazene_pozice:
                    velikost = _velikost_pro_bunku(
                        text, dostupna, velikost_akordu, TECHNICKY_MIN_VELIKOST
                    )
                    c.setFont(FONT_AKORD, velikost)
                    c.setFillColorRGB(*BARVA_CERNA)
                    c.drawString(x + x_offset + 3, y_radku - chord_offset, text)
                    skutecne_konce[idx_doby] = (
                        x + x_offset + 3 + pdfmetrics.stringWidth(text, FONT_AKORD, velikost)
                    )

                # tečky v prázdných dobách — ne, když do nich zasahuje
                # přetékající akord PŘEDCHOZÍ obsazené doby (viz zadání)
                posledni_konec = None
                for doba in range(dob_taktu):
                    if doba in obsazene_indexy:
                        posledni_konec = skutecne_konce[doba]
                        continue
                    x_stred = x + doba * sirka_doby + sirka_doby / 2
                    if posledni_konec is not None and posledni_konec > x_stred:
                        continue  # akord z předchozí doby sem zasahuje — má přednost
                    c.setFillColorRGB(*BARVA_SEDA)
                    c.circle(
                        x_stred,
                        y_radku - chord_offset + velikost_akordu * 0.32,
                        max(1.6 * scale, 0.6),
                        stroke=0,
                        fill=1,
                    )

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
                    sirka_doby=sirka_doby,
                    radek=radek,
                    takt_vychozi=takt_vychozi,
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


def _x_pozice_taktu(radek, takt_vychozi, sirka_doby, index_taktu):
    """X offset (od začátku řádku) taktu na daném indexu — potřebuje sečíst
    šířky VŠECH předchozích taktů (ty mohou mít různý dob, viz vlastní takt)."""
    x = 0
    for t in radek["takty"][:index_taktu]:
        x += _efektivni_takt(t, takt_vychozi)["dob"] * sirka_doby
    return x


def _kresli_repetici(
    c,
    x0,
    y_radku,
    vyska_radku,
    sirka_doby,
    radek,
    takt_vychozi,
    od_v_radku,
    do_v_radku,
    kresli_zacatek,
    kresli_konec,
    krat,
    velikost_repetice_n,
    chord_offset,
):
    """Tlustá čára + dvě tečky na začátku a konci rozsahu, ×N vpravo od
    konce. Rozsah je už OŘÍZNUTÝ na tenhle řádek (viz volající) — repetice
    přesahující přes víc řádků nakreslí začátek/konec jen tam, kam patří."""
    x_zacatek = x0 + _x_pozice_taktu(radek, takt_vychozi, sirka_doby, od_v_radku)
    x_konec = x0 + _x_pozice_taktu(radek, takt_vychozi, sirka_doby, do_v_radku + 1)
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
