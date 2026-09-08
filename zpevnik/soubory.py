"""Chráněné servírování souborů.

Django soubor sám neposílá — blokoval by tím gunicorn worker na celou dobu
přenosu. Místo toho ověří práva a vrátí prázdnou odpověď s hlavičkou
`X-Accel-Redirect`; soubor pak ze složky pošle nginx, který to umí.

Nginx vhost (viz our-hub/infra/nginx/zpevnik.upupaepops.cz.conf):

    location /protected/ {
        internal;
        alias /opt/zpevnik/media/;
    }

`internal` znamená, že /protected/ nejde zvenčí zavolat přímo — jen jako
následek X-Accel-Redirect z Djanga. Proto ve vhostu nesmí vzniknout žádný
`location /media/`, který by stejné soubory servíroval bez kontroly práv.
"""

import os
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse

from .models import VerzePisne


def smi_cist_verzi(user, verze):
    """Personal verze je soukromá (vlastník + admin), ostatní vidí každý přihlášený."""
    if not (user and user.is_authenticated):
        return False
    if verze.stav == VerzePisne.STAV_PERSONAL:
        return bool(user.is_staff or verze.vlastnik_id == user.id)
    return True


def _hlavicka_disposition(nazev_k_zobrazeni):
    """`inline` — čtečka má PDF zobrazit, ne nabídnout ke stažení."""
    bezpecny = nazev_k_zobrazeni or "noty.pdf"
    # filename* kvůli diakritice v názvech písní (RFC 5987).
    return f"inline; filename*=UTF-8''{quote(bezpecny)}"


def odpoved_se_souborem(verze):
    """Odpověď, která nechá soubor poslat nginx.

    Cesta v X-Accel-Redirect se skládá **výhradně z hodnoty v databázi**
    (`verze.soubor.name`), nikdy z parametru requestu. Klient volí jen to,
    o kterou verzi si řekne — a jestli na ni má právo, se rozhoduje dřív,
    než se sem vůbec dostane.
    """
    if not verze.soubor:
        raise Http404("Verze nemá nahraný soubor.")

    nazev = verze.soubor.name

    # Obrana do hloubky: cesta z DB musí zůstat relativní a bez '..'. Když se sem
    # něco takového dostane, je to bug jinde — a nesmí skončit servírováním
    # souboru mimo media složku.
    if nazev.startswith("/") or nazev.startswith("\\") or ".." in nazev.replace("\\", "/").split("/"):
        raise Http404("Neplatná cesta k souboru.")

    disposition = _hlavicka_disposition(
        verze.puvodni_nazev_souboru or os.path.basename(nazev)
    )

    if settings.X_ACCEL_REDIRECT:
        odpoved = HttpResponse(content_type="application/pdf")
        odpoved["X-Accel-Redirect"] = settings.X_ACCEL_PREFIX + quote(nazev)
        odpoved["Content-Disposition"] = disposition
        return odpoved

    # Nouzový režim pro lokální vývoj, kde nginx neběží. V produkci musí být
    # X_ACCEL_REDIRECT=True — hlídá to i system check zpevnik.E001 v apps.py.
    if not verze.soubor.storage.exists(nazev):
        raise Http404("Soubor na disku neexistuje.")
    odpoved = FileResponse(verze.soubor.open("rb"), content_type="application/pdf")
    odpoved["Content-Disposition"] = disposition
    return odpoved
