"""Validace nahrávaných souborů.

Zásada: nevěřit ničemu, co přijde od klienta — ani příponě, ani hlavičce
`Content-Type` v requestu. Rozhoduje obsah souboru a limity ze settings.
"""

from django.conf import settings
from rest_framework import serializers

# PDF podle specifikace začíná "%PDF-" (magic bytes).
PDF_MAGIC = b"%PDF-"


def bezpecny_puvodni_nazev(nazev):
    """Očistí jméno souboru od klienta na holý basename pro zobrazení v UI.

    Jméno se NIKDY nepoužívá pro cestu na disku (tu generuje server, viz
    `cesta_pro_soubor_verze`), tohle je jen kosmetika do DB. Přesto ho čistíme —
    ať se do DB nedostane "../../etc/passwd" a nikdo ho pak omylem nespojí s cestou.
    """
    if not nazev:
        return ""

    # Klient může poslat oddělovače unixové i windowsové — ber jen poslední komponentu.
    posledni = str(nazev).replace("\\", "/").split("/")[-1]
    # Pryč s řídicími znaky a nulovým bajtem.
    posledni = "".join(z for z in posledni if z.isprintable()).strip()

    if posledni in ("", ".", ".."):
        return ""
    return posledni[:255]


def zvaliduj_pdf(soubor):
    """Ověří, že nahraný soubor je neprázdné PDF v povoleném limitu velikosti.

    Kontroluje se obsah (magic bytes), ne přípona — soubor přejmenovaný
    na .pdf tudy neprojde.
    """
    if soubor.size == 0:
        raise serializers.ValidationError("Soubor je prázdný.")

    if soubor.size > settings.MAX_UPLOAD_SIZE:
        limit_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise serializers.ValidationError(
            f"Soubor je příliš velký (limit je {limit_mb:.0f} MB)."
        )

    zacatek = soubor.read(len(PDF_MAGIC))
    soubor.seek(0)  # ať navazující uložení čte od začátku
    if zacatek != PDF_MAGIC:
        raise serializers.ValidationError(
            "Soubor není PDF (nesouhlasí obsah, ne jen přípona)."
        )

    return soubor
