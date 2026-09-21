"""Generuje PDF akordového zápisu (viz PC_zpevnik_akordovy_zapis.md).

reportlab, NE weasyprint — ten by potřeboval systémové knihovny navíc v
Docker image. Fonty jsou přibalené v repu (zpevnik/fonts/, viz LICENSE.md
tam), žádné systémové — jinak by vzhled záležel na tom, co je zrovna
nainstalované na serveru.

Kreslí se přímo přes nízkoúrovňové Canvas API (ne platypus/flowables) —
mřížka akordů s ručním zalamováním řádků a stránek potřebuje přesnou
kontrolu pozic, kterou by flowables jen zbytečně komplikovaly.
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
    # Registrace je globální (per proces) a idempotentní — bez tyhle stráže
    # by druhé volání v témže procesu (gunicorn worker obsluhující víc
    # requestů) spadlo na "font already registered", i když by nic nevadilo.
    global _fonty_zaregistrovany
    if _fonty_zaregistrovany:
        return
    pdfmetrics.registerFont(TTFont(FONT_AKORD, os.path.join(FONTS_DIR, "Carlito-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_POPISEK, os.path.join(FONTS_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(
        TTFont(FONT_POPISEK_TUCNE, os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf"))
    )
    _fonty_zaregistrovany = True


# --- rozměry (body, A4 = 595 x 842) ---
# Kalibrováno na referenční africa_chord_chart.pdf (jen VZHLED — hlavička,
# tloušťky čar, velikosti písma a rozestupy řádků; MŘÍŽKU si necháváme
# vlastní, buňka = doba, ne takt — viz zadání). Přesné hodnoty (font-size,
# pozice čar, výška řádku) zjištěné rozborem té PDF přes PyMuPDF
# (get_text/get_drawings), ne odhadem od oka.
SIRKA_STRANKY, VYSKA_STRANKY = A4
OKRAJ = 30
SIRKA_GUTTERU = 70  # levý sloupec se sekcí
# Cíl hustoty řádku: 4 takty 4/4 na řádek A4 při 17.5pt (viz zadání) — takt
# má v 4/4 čtyři doby, takže "4 takty" = 16 dob. Řádek se ROZPOČÍTÁ na tenhle
# počet dob bez ohledu na takt (viz taktu_na_radek níž): 3/4 se vejde víc
# taktů na řádek (16 // 3 = 5), 6/8 míň (16 // 6 = 2) — šířka taktu/doby se
# pak dopočítá tak, aby PŘESNĚ vyplnila dostupnou šířku, ne aby nechávala
# místo navíc.
DOBY_NA_RADEK = 16
VYSKA_RADKU = 28  # výška jedné VIZUÁLNÍ linky s akordy (po zalomení)
MEZERA_ZALOMENI = 4  # mezi zalomenými pokračováními TÉHOŽ logického řádku
MEZERA_RADKU = 11  # mezi dvěma RŮZNÝMI logickými řádky (víc než při zalomení)
# Baseline uvnitř řádkového pásu VYSKA_RADKU — akordy i ×N na stejné výšce
# jako v referenci, sekce jen nepatrně výš (menší font, opticky vyrovnané).
CHORD_BASELINE_OFFSET = 19
SEKCE_BASELINE_OFFSET = 18

VELIKOST_TITULKU = 26
VELIKOST_INTERPRETA = 13
VELIKOST_SEKCE = 11
VELIKOST_AKORDU = 17.5  # z reference — NE odhad
MIN_VELIKOST_AKORDU = 10
VELIKOST_REPETICE_N = 16

TLOUSTKA_CARY = 0.8  # obyčejná dělicí čára taktu — z reference ČERNÁ, ne šedá
TLOUSTKA_REPETICE = 2.2
TLOUSTKA_PRAVITKA = 1.2  # čára pod hlavičkou

BARVA_SEDA = (0.3, 0.3, 0.3)  # sekce, interpret, tempo — z reference (~76–89/255)
BARVA_CERNA = (0, 0, 0)

REZERVA_MEZI_AKORDY = 5  # mezera před dalším obsazeným akordem / koncem taktu


def _pozice_v_taktu(bunky_taktu, sirka_doby, sirka_taktu):
    """Pro každou OBSAZENOU dobu v taktu vrátí (text, x_offset, dostupna_sirka).

    Dostupná šířka sahá až k DALŠÍ obsazené době v tomtéž taktu, nebo (není-li
    žádná) ke konci taktu — mezi jednotlivými dobami se nekreslí žádná čára
    (ta je jen mezi takty), takže akord smí vizuálně přetéct do prázdných dob
    za sebou. Zmenšuje se teprve, když by nezůstal ani v tomhle prostoru
    (viz zadání)."""
    obsazene = [i for i, text in enumerate(bunky_taktu) if text]
    vysledek = []
    for poradi, i in enumerate(obsazene):
        x_offset = i * sirka_doby
        pristi = obsazene[poradi + 1] * sirka_doby if poradi + 1 < len(obsazene) else sirka_taktu
        vysledek.append((bunky_taktu[i], x_offset, pristi - x_offset))
    return vysledek


def _velikost_pro_bunku(text, dostupna_sirka):
    """Jednotná velikost pro celý dokument, POKUD se text vejde do dostupné
    šířky (až k další obsazené době nebo konci taktu, viz _pozice_v_taktu,
    s rezervou na mezeru) — jinak se zmenšuje, dokud se nevejde. Jen tahle
    buňka, ne celý dokument (viz zadání: "buňky s dlouhým obsahem smí mít
    menší písmo, ale jen ty")."""
    velikost = VELIKOST_AKORDU
    limit = dostupna_sirka - REZERVA_MEZI_AKORDY
    while velikost > MIN_VELIKOST_AKORDU and pdfmetrics.stringWidth(
        text, FONT_AKORD, velikost
    ) > limit:
        velikost -= 0.5
    return velikost


def _rozloz_takty_do_radku(pocet_taktu, taktu_na_radek):
    """Vizuální zalomení dlouhého řádku — (od, do) rozsahy taktů, 0-based,
    `do` VYLOUČENÉ, po nejvýš `taktu_na_radek` kusech."""
    if pocet_taktu == 0:
        return [(0, 0)]
    vysledek = []
    start = 0
    while start < pocet_taktu:
        konec = min(start + taktu_na_radek, pocet_taktu)
        vysledek.append((start, konec))
        start = konec
    return vysledek


def _vyska_logickeho_radku(pocet_taktu, taktu_na_radek):
    pocet_vizualnich = len(_rozloz_takty_do_radku(pocet_taktu, taktu_na_radek))
    return pocet_vizualnich * VYSKA_RADKU + (pocet_vizualnich - 1) * MEZERA_ZALOMENI


def vygeneruj_pdf(pisen, akordy):
    """`pisen` — instance Pisen (název, interpret). `akordy` — JSON prošlý
    přes AkordovyZapisSerializer (dělitelnost taktů i hranice repetic už
    ověřené). Vrací bytes hotového PDF."""
    _zaregistruj_fonty()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    dob = akordy["takt"]["dob"]
    hodnota = akordy["takt"]["hodnota"]
    tempo = akordy.get("tempo")
    radky = akordy["radky"]

    sirka_obsahu = SIRKA_STRANKY - 2 * OKRAJ - SIRKA_GUTTERU
    # Cíl: `DOBY_NA_RADEK` dob na řádek bez ohledu na takt (16 // 4 = přesně
    # 4 takty 4/4). Šířka taktu/doby se PAK dopočítá tak, aby těch
    # `taktu_na_radek` taktů přesně vyplnilo dostupnou šířku (viz zadání:
    # "šířka taktu = dostupná šířka / 4 pro 4/4") — ne naopak.
    taktu_na_radek = max(1, DOBY_NA_RADEK // dob)
    sirka_taktu = sirka_obsahu / taktu_na_radek
    sirka_doby = sirka_taktu / dob
    x0 = OKRAJ + SIRKA_GUTTERU
    dolni_limit = OKRAJ + VYSKA_RADKU

    def kresli_hlavicku():
        # Titulek a interpret sdílejí JEDNU baseline (interpret hned za
        # titulkem, ne pod ním) — stejně jako tempo/takt vpravo, viz reference.
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
        text_taktu = f"{dob}/{hodnota}"
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

    if not radky:
        c.showPage()
        c.save()
        return buffer.getvalue()

    for radek in radky:
        pocet_taktu = len(radek["bunky"]) // dob
        vizualni = _rozloz_takty_do_radku(pocet_taktu, taktu_na_radek)

        # Celý logický řádek se musí vejít na jednu stránku — nezalamovat
        # stránku uprostřed řádku (viz zadání).
        if y - _vyska_logickeho_radku(pocet_taktu, taktu_na_radek) < dolni_limit:
            y = nova_stranka()

        for idx_vizualni, (od, do) in enumerate(vizualni):
            y_radku = y

            if idx_vizualni == 0 and radek.get("sekce"):
                c.setFont(FONT_POPISEK_TUCNE, VELIKOST_SEKCE)
                c.setFillColorRGB(*BARVA_SEDA)
                c.drawString(OKRAJ, y_radku - SEKCE_BASELINE_OFFSET, radek["sekce"].upper())

            c.setStrokeColorRGB(*BARVA_CERNA)
            c.setLineWidth(TLOUSTKA_CARY)
            x = x0
            c.line(x, y_radku - VYSKA_RADKU, x, y_radku)  # levý okraj prvního taktu
            for i_takt in range(od, do):
                bunky_taktu = radek["bunky"][i_takt * dob : i_takt * dob + dob]
                for text, x_offset, dostupna_sirka in _pozice_v_taktu(bunky_taktu, sirka_doby, sirka_taktu):
                    velikost = _velikost_pro_bunku(text, dostupna_sirka)
                    c.setFont(FONT_AKORD, velikost)
                    c.setFillColorRGB(*BARVA_CERNA)
                    c.drawString(x + x_offset + 3, y_radku - CHORD_BASELINE_OFFSET, text)
                x += sirka_taktu
                c.line(x, y_radku - VYSKA_RADKU, x, y_radku)

            for rep in radek.get("repetice", []):
                seg_od = max(rep["od_taktu"], od)
                seg_do = min(rep["do_taktu"], do - 1)
                if seg_od > seg_do:
                    continue  # repetice do tohohle vizuálního úseku vůbec nezasahuje
                _kresli_repetici(
                    c,
                    x0=x0,
                    y_radku=y_radku,
                    sirka_taktu=sirka_taktu,
                    od_v_useku=seg_od - od,
                    do_v_useku=seg_do - od,
                    kresli_zacatek=rep["od_taktu"] >= od,
                    kresli_konec=rep["do_taktu"] < do,
                    krat=rep["krat"],
                )

            y -= VYSKA_RADKU + MEZERA_ZALOMENI

        y += MEZERA_ZALOMENI  # poslední přírůstek zalomení zrušit
        y -= MEZERA_RADKU

    c.showPage()
    c.save()
    return buffer.getvalue()


def _kresli_repetici(
    c, x0, y_radku, sirka_taktu, od_v_useku, do_v_useku, kresli_zacatek, kresli_konec, krat
):
    """Tlustá čára + dvě tečky na začátku a konci rozsahu, ×N vpravo od
    konce — tloušťka i teček podle reference. Rozsah předaný sem je už
    OŘÍZNUTÝ na aktuální vizuální řádek (viz volající) — u repetice
    přesahující přes zalomení se značka začátku/konce nakreslí jen na tom
    úseku, kam skutečně patří."""
    x_zacatek = x0 + od_v_useku * sirka_taktu
    x_konec = x0 + (do_v_useku + 1) * sirka_taktu
    y_tecka_horni = y_radku - VYSKA_RADKU * 0.35
    y_tecka_dolni = y_radku - VYSKA_RADKU * 0.65

    c.setStrokeColorRGB(*BARVA_CERNA)
    c.setLineWidth(TLOUSTKA_REPETICE)
    c.setFillColorRGB(*BARVA_CERNA)

    if kresli_zacatek:
        c.line(x_zacatek, y_radku - VYSKA_RADKU, x_zacatek, y_radku)
        c.circle(x_zacatek + 4.5, y_tecka_horni, 1.6, stroke=0, fill=1)
        c.circle(x_zacatek + 4.5, y_tecka_dolni, 1.6, stroke=0, fill=1)

    if kresli_konec:
        c.line(x_konec, y_radku - VYSKA_RADKU, x_konec, y_radku)
        c.circle(x_konec - 4.5, y_tecka_horni, 1.6, stroke=0, fill=1)
        c.circle(x_konec - 4.5, y_tecka_dolni, 1.6, stroke=0, fill=1)
        c.setFont(FONT_POPISEK_TUCNE, VELIKOST_REPETICE_N)
        c.drawString(x_konec + 8, y_radku - CHORD_BASELINE_OFFSET, f"×{krat}")
