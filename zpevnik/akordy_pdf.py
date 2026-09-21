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
SIRKA_STRANKY, VYSKA_STRANKY = A4
OKRAJ = 40
SIRKA_GUTTERU = 72  # levý sloupec se sekcí
SIRKA_DOBY = 27  # šířka jedné doby (beat) v taktu
VYSKA_RADKU = 26  # výška jedné VIZUÁLNÍ linky s akordy (po zalomení)
MEZERA_ZALOMENI = 4  # mezi zalomenými pokračováními TÉHOŽ logického řádku
MEZERA_RADKU = 14  # mezi dvěma RŮZNÝMI logickými řádky (víc než při zalomení)

VELIKOST_AKORDU = 11
MIN_VELIKOST_AKORDU = 7
BARVA_SEDA = (0.45, 0.45, 0.45)
BARVA_CERNA = (0, 0, 0)


def _velikost_pro_bunku(text):
    """Jednotná velikost pro celý dokument, POKUD se text vejde do šířky
    jedné doby (s rezervou na mezery mezi sousedními akordy) — jinak se
    zmenšuje, dokud se nevejde. Jen tahle buňka, ne celý dokument (viz
    zadání: "buňky s dlouhým obsahem smí mít menší písmo, ale jen ty")."""
    velikost = VELIKOST_AKORDU
    limit = SIRKA_DOBY - 4
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
    taktu_na_radek = max(1, int(sirka_obsahu // (dob * SIRKA_DOBY)))
    x0 = OKRAJ + SIRKA_GUTTERU
    dolni_limit = OKRAJ + VYSKA_RADKU

    def kresli_hlavicku():
        c.setFont(FONT_POPISEK_TUCNE, 20)
        c.setFillColorRGB(*BARVA_CERNA)
        c.drawString(OKRAJ, VYSKA_STRANKY - OKRAJ, pisen.nazev)
        if pisen.interpret:
            c.setFont(FONT_POPISEK, 12)
            c.setFillColorRGB(*BARVA_SEDA)
            c.drawString(OKRAJ, VYSKA_STRANKY - OKRAJ - 18, pisen.interpret)
        c.setFont(FONT_POPISEK, 11)
        c.setFillColorRGB(*BARVA_CERNA)
        text_taktu = f"{dob}/{hodnota}"
        if tempo:
            text_taktu = f"♩ = {tempo} · {text_taktu}"
        c.drawRightString(SIRKA_STRANKY - OKRAJ, VYSKA_STRANKY - OKRAJ, text_taktu)
        return VYSKA_STRANKY - OKRAJ - 44

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
                c.setFont(FONT_POPISEK_TUCNE, 9)
                c.setFillColorRGB(*BARVA_SEDA)
                c.drawString(OKRAJ, y_radku - 9, radek["sekce"].upper())

            c.setStrokeColorRGB(*BARVA_SEDA)
            c.setLineWidth(0.6)
            x = x0
            c.line(x, y_radku - 20, x, y_radku)  # levý okraj prvního taktu na řádku
            for i_takt in range(od, do):
                for doba in range(dob):
                    text = radek["bunky"][i_takt * dob + doba]
                    if text:
                        velikost = _velikost_pro_bunku(text)
                        c.setFont(FONT_AKORD, velikost)
                        c.setFillColorRGB(*BARVA_CERNA)
                        c.drawString(x + doba * SIRKA_DOBY + 2, y_radku - 14, text)
                x += dob * SIRKA_DOBY
                c.line(x, y_radku - 20, x, y_radku)

            for rep in radek.get("repetice", []):
                seg_od = max(rep["od_taktu"], od)
                seg_do = min(rep["do_taktu"], do - 1)
                if seg_od > seg_do:
                    continue  # repetice do tohohle vizuálního úseku vůbec nezasahuje
                _kresli_repetici(
                    c,
                    x0=x0,
                    y_radku=y_radku,
                    dob=dob,
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


def _kresli_repetici(c, x0, y_radku, dob, od_v_useku, do_v_useku, kresli_zacatek, kresli_konec, krat):
    """Tlustá čára + dvě tečky na začátku a konci rozsahu, ×N vpravo od
    konce. Rozsah předaný sem je už OŘÍZNUTÝ na aktuální vizuální řádek
    (viz volající) — u repetice přesahující přes zalomení se značka
    začátku/konce nakreslí jen na tom úseku, kam skutečně patří."""
    sirka_taktu = dob * SIRKA_DOBY
    x_zacatek = x0 + od_v_useku * sirka_taktu
    x_konec = x0 + (do_v_useku + 1) * sirka_taktu

    c.setStrokeColorRGB(*BARVA_CERNA)
    c.setLineWidth(2)
    c.setFillColorRGB(*BARVA_CERNA)

    if kresli_zacatek:
        c.line(x_zacatek, y_radku - 20, x_zacatek, y_radku)
        c.circle(x_zacatek + 4, y_radku - 7, 1.3, stroke=0, fill=1)
        c.circle(x_zacatek + 4, y_radku - 13, 1.3, stroke=0, fill=1)

    if kresli_konec:
        c.line(x_konec, y_radku - 20, x_konec, y_radku)
        c.circle(x_konec - 4, y_radku - 7, 1.3, stroke=0, fill=1)
        c.circle(x_konec - 4, y_radku - 13, 1.3, stroke=0, fill=1)
        c.setFont(FONT_POPISEK, 9)
        c.drawString(x_konec + 4, y_radku - 14, f"×{krat}")
