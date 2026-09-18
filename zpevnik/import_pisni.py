"""Hromadný import zpěvníku z jednoho PDF (fáze 1e).

Parsování textu (hledání kódu/názvu/interpreta v hlavičce stránky) proběhlo
na klientovi přes PDF.js — 88stránkové PDF by se v jednom HTTP requestu
nestihlo zpracovat rozumně. Sem přichází až POTVRZENÝ plán (uživatel prošel
kontrolní tabulku) a originální soubor. Server plánu věří v tom, co stejně
nejde ověřit líp než člověk (kód/název/interpret) — sám jen fyzicky rozřeže
PDF a ověří to, co levně ověřit jde: rozsahy stránek a unikátnost kódů.

Idempotence: kód písně je jediný smysluplný přirozený klíč, který import má
k dispozici (`Pisen.kod` je navíc unique i na úrovni DB). Import se PŘED
založením čehokoliv podívá, jestli některý z plánovaných kódů už v databázi
není — pokud ano, celý import se odmítne (nic se nezaloží) s seznamem
kolidujících kódů. Druhé spuštění se stejným (nebo překrývajícím se) plánem
tak nikdy nevyrobí duplicitní písně — buď se nic nestane (a je jasné proč),
nebo uživatel kódy v tabulce oprav a doimportuje jen nové písně.
"""

import io

from django.core.files.base import ContentFile
from django.db import transaction
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from rest_framework.exceptions import ValidationError

from .models import Pisen, Slozka, VerzePisne, Zpevnik
from .validatory import PDF_MAGIC, zvaliduj_pdf


def proved_import(soubor_pdf, plan):
    """`plan` je už projitý přes `ImportPlanSerializer.validated_data`:

        {
          "pisne": [{"kod": int, "nazev": str, "interpret": str, "stranky": [int, ...]}, ...],
          "kategorie": [{"digit": "1".."5", "nazev": str, "vytvorit": bool}, ...],
          "cely_zpevnik": {"nazev": str, "vytvorit": bool} | None,
        }

    `kategorie` vyrábí PRO PROHLÍŽENÍ podle první číslice kódu — vlastní
    Slozka + Zpevnik na kategorii, protože Slozka sama o sobě písně držet
    neumí (jen Zpevnik). `cely_zpevnik` navíc založí (nebo doplní, pokud už
    existuje) JEDEN Zpevnik se všemi importovanými písněmi — ten je "ta
    kniha jako celek", na kterou má smysl navázat setlist nebo vygenerovat
    jeden veřejný QR odkaz. Píseň může být v obou zároveň (M2M), takže se
    tím nic neztrácí.

    Vrací dict {"pisne": [Pisen, ...], "slozky": [Slozka, ...], "zpevniky": [Zpevnik, ...]}.
    Při jakékoliv chybě vyhodí `ValidationError` a NEZALOŽÍ nic — buď projde
    celý import, nebo žádná jeho část.
    """
    soubor_pdf.seek(0)
    if soubor_pdf.size == 0:
        raise ValidationError({"soubor": ["Soubor je prázdný."]})
    if soubor_pdf.read(len(PDF_MAGIC)) != PDF_MAGIC:
        raise ValidationError(
            {"soubor": ["Soubor není PDF (nesouhlasí obsah, ne jen přípona)."]}
        )
    soubor_pdf.seek(0)

    try:
        reader = PdfReader(soubor_pdf)
        pocet_stran = len(reader.pages)
    except PdfReadError as chyba:
        raise ValidationError({"soubor": [f"PDF se nepodařilo otevřít: {chyba}"]})

    pisne_plan = plan["pisne"]
    kategorie_plan = plan.get("kategorie") or []
    cely_zpevnik_plan = plan.get("cely_zpevnik")

    _zkontroluj_plan(pisne_plan, pocet_stran)

    # --- rozřezání PDF (CPU/IO, žádné DB zápisy — mimo transakci schválně) ---
    narezane = []
    for polozka in pisne_plan:
        writer = PdfWriter()
        for strana in polozka["stranky"]:
            writer.add_page(reader.pages[strana - 1])
        buffer = io.BytesIO()
        writer.write(buffer)
        obsah = ContentFile(buffer.getvalue(), name=f"import-{polozka['kod']}.pdf")
        # Stejná validace jako běžný jednotlivý upload — žádná druhá cesta k disku.
        zvaliduj_pdf(obsah)
        narezane.append((polozka, obsah))

    # --- založení, atomicky: buď projde všechno, nebo nic ---
    vytvorene_pisne = []
    vytvorene_slozky = []
    vytvorene_zpevniky = []
    with transaction.atomic():
        for polozka, obsah in narezane:
            pisen = Pisen.objects.create(
                kod=polozka["kod"],
                nazev=polozka["nazev"],
                interpret=polozka.get("interpret", ""),
            )
            VerzePisne.objects.create(
                pisen=pisen,
                typ_obsahu=VerzePisne.TYP_PDF,
                soubor=obsah,
                stav=VerzePisne.STAV_DOWNLOAD,
            )
            vytvorene_pisne.append(pisen)

        for kat in kategorie_plan:
            if not kat.get("vytvorit", True):
                continue
            pisne_v_kategorii = [
                p for p in vytvorene_pisne if str(p.kod)[0] == kat["digit"]
            ]
            if not pisne_v_kategorii:
                continue
            # get_or_create záměrně — opakovaný import (nové kódy do stejné
            # kategorie) přiřadí do STEJNÉ složky/zpěvníku, nevyrobí duplicitní.
            slozka, _ = Slozka.objects.get_or_create(nazev=kat["nazev"])
            zpevnik, _ = Zpevnik.objects.get_or_create(
                nazev=kat["nazev"], slozka=slozka
            )
            zpevnik.pisne.add(*pisne_v_kategorii)
            vytvorene_slozky.append(slozka)
            vytvorene_zpevniky.append(zpevnik)

        if cely_zpevnik_plan and cely_zpevnik_plan.get("vytvorit", True):
            # Bez slozka v lookupu schválně — "celá kniha" je vědomě
            # top-level, žádná kategorie ji nemá obalovat. get_or_create podle
            # názvu (ne id) je to, co dělá opakovaný import idempotentní i
            # tady: doimportované písně přibydou do STEJNÉHO zpěvníku.
            cely_zpevnik, _ = Zpevnik.objects.get_or_create(
                nazev=cely_zpevnik_plan["nazev"]
            )
            cely_zpevnik.pisne.add(*vytvorene_pisne)
            vytvorene_zpevniky.append(cely_zpevnik)

    return {
        "pisne": vytvorene_pisne,
        "slozky": vytvorene_slozky,
        "zpevniky": vytvorene_zpevniky,
    }


def _zkontroluj_plan(pisne_plan, pocet_stran):
    if not pisne_plan:
        raise ValidationError({"pisne": ["Plán neobsahuje žádnou píseň."]})

    kody = [p["kod"] for p in pisne_plan]
    duplicitni_v_planu = sorted({k for k in kody if kody.count(k) > 1})
    if duplicitni_v_planu:
        raise ValidationError(
            {
                "pisne": [
                    f"Tyhle kódy se v importu opakují víckrát: {duplicitni_v_planu}."
                ]
            }
        )

    jiz_v_db = sorted(
        Pisen.objects.filter(kod__in=kody).values_list("kod", flat=True)
    )
    if jiz_v_db:
        raise ValidationError(
            {
                "pisne": [
                    f"Tyhle kódy už v databázi existují, import by je zdvojil: "
                    f"{jiz_v_db}. Oprav je v tabulce (nebo je z importu vyřaď) "
                    f"a zkus to znovu."
                ]
            }
        )

    vsechny_stranky = []
    for p in pisne_plan:
        if not p["stranky"]:
            raise ValidationError(
                {"pisne": [f"Píseň s kódem {p['kod']} nemá žádnou stránku."]}
            )
        for strana in p["stranky"]:
            if strana < 1 or strana > pocet_stran:
                raise ValidationError(
                    {
                        "pisne": [
                            f"Strana {strana} u kódu {p['kod']} je mimo rozsah "
                            f"nahraného PDF (1–{pocet_stran})."
                        ]
                    }
                )
        vsechny_stranky.extend(p["stranky"])

    duplicitni_stranky = sorted(
        {s for s in vsechny_stranky if vsechny_stranky.count(s) > 1}
    )
    if duplicitni_stranky:
        raise ValidationError(
            {
                "pisne": [
                    f"Tyhle strany jsou přiřazené víc než jedné písni: {duplicitni_stranky}."
                ]
            }
        )
