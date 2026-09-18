"""Hromadný import zpěvníku z jednoho PDF (fáze 1e, kódy per zpěvník od 2b).

Parsování textu (hledání kódu/názvu/interpreta v hlavičce stránky) proběhlo
na klientovi přes PDF.js — 88stránkové PDF by se v jednom HTTP requestu
nestihlo zpracovat rozumně. Sem přichází až POTVRZENÝ plán (uživatel prošel
kontrolní tabulku) a originální soubor. Server plánu věří v tom, co stejně
nejde ověřit líp než člověk (kód/název/interpret) — sám jen fyzicky rozřeže
PDF a ověří to, co levně ověřit jde: rozsahy stránek a unikátnost kódů.

Kód je od fáze 2b vlastnost zařazení do KONKRÉTNÍHO zpěvníku (PolozkaZpevniku),
ne písně — dvě různé knihy si tak nepřekáží ve vlastním číslování a nový
zpěvník bez vlastních čísel může vždycky čistě začít od 100/101, ať v
databázi existuje cokoliv jiného.

Idempotence: kolize se kontroluje jen proti zpěvníkům, které import osloví
JMÉNEM a které DB už obsahuje (nový zpěvník je prázdný, tam kolidovat není
s čím). Pokud tam kterýkoliv z plánovaných kódů už je, celý import se
odmítne (nic se nezaloží) se seznamem kolidujících kódů a zpěvníku, kde jsou.
Druhé spuštění se stejným (nebo překrývajícím se) plánem do TÉHOŽ zpěvníku
tak nikdy nevyrobí duplicitní čísla — buď se nic nestane (a je jasné proč),
nebo uživatel kódy v tabulce oprav a doimportuje jen nové písně.
"""

import io

from django.core.files.base import ContentFile
from django.db import transaction
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from rest_framework.exceptions import ValidationError

from .models import Pisen, PolozkaZpevniku, Slozka, VerzePisne, Zpevnik
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

    _zkontroluj_plan(pisne_plan, pocet_stran, kategorie_plan, cely_zpevnik_plan)

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
    # kód z plánu si pisen.kod už neponese (ten na Pisen vůbec není) — dokud
    # se píseň nezařadí do zpěvníku (PolozkaZpevniku), musí se pamatovat
    # zvlášť podle PK nově vytvořené písně.
    kod_podle_pisne = {}
    with transaction.atomic():
        for polozka, obsah in narezane:
            pisen = Pisen.objects.create(
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
            kod_podle_pisne[pisen.id] = polozka["kod"]

        for kat in kategorie_plan:
            if not kat.get("vytvorit", True):
                continue
            pisne_v_kategorii = [
                p for p in vytvorene_pisne if str(kod_podle_pisne[p.id])[0] == kat["digit"]
            ]
            if not pisne_v_kategorii:
                continue
            # get_or_create záměrně — opakovaný import (nové kódy do stejné
            # kategorie) přiřadí do STEJNÉ složky/zpěvníku, nevyrobí duplicitní.
            slozka, _ = Slozka.objects.get_or_create(nazev=kat["nazev"])
            zpevnik, _ = Zpevnik.objects.get_or_create(
                nazev=kat["nazev"], slozka=slozka
            )
            # Ne zpevnik.pisne.add(*pisne) — M2M s `through`, co má navíc
            # povinné pole (kód), takové hromadné `.add()` neumí (dal by
            # všem stejnou hodnotu). Řádek po řádku, každý se svým kódem.
            for p in pisne_v_kategorii:
                PolozkaZpevniku.objects.create(
                    zpevnik=zpevnik, pisen=p, kod=kod_podle_pisne[p.id]
                )
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
            for p in vytvorene_pisne:
                PolozkaZpevniku.objects.create(
                    zpevnik=cely_zpevnik, pisen=p, kod=kod_podle_pisne[p.id]
                )
            vytvorene_zpevniky.append(cely_zpevnik)

    return {
        "pisne": vytvorene_pisne,
        "slozky": vytvorene_slozky,
        "zpevniky": vytvorene_zpevniky,
        # Kód z plánu — pro odpověď API (Pisen sám o sobě kód nenese, viz výš).
        "kod_podle_pisne": kod_podle_pisne,
    }


def _zkontroluj_plan(pisne_plan, pocet_stran, kategorie_plan, cely_zpevnik_plan):
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

    # Kolize s DB: kód je teď vlastnost zařazení do KONKRÉTNÍHO zpěvníku, ne
    # písně — kontroluje se proto jen proti zpěvníkům, které tenhle import
    # osloví jménem A které DB už obsahuje. Nově založený zpěvník je prázdný,
    # tam kolidovat není s čím (proto může nová kniha bez vlastních kódů
    # vždycky čistě začít na 100/101, ať už v DB existuje cokoliv jiného).
    cilove_nazvy = {
        kat["nazev"] for kat in kategorie_plan if kat.get("vytvorit", True)
    }
    if cely_zpevnik_plan and cely_zpevnik_plan.get("vytvorit", True):
        cilove_nazvy.add(cely_zpevnik_plan["nazev"])

    for zpevnik in Zpevnik.objects.filter(nazev__in=cilove_nazvy):
        obsazene = set(zpevnik.polozky.values_list("kod", flat=True))
        kolize = sorted(obsazene & set(kody))
        if kolize:
            raise ValidationError(
                {
                    "pisne": [
                        f"Ve zpěvníku „{zpevnik.nazev}“ už tyhle kódy existují, "
                        f"import by je zdvojil: {kolize}. Oprav je v tabulce "
                        f"(nebo je z importu vyřaď) a zkus to znovu."
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
