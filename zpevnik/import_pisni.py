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

CÍLOVÝ zpěvník (`cely_zpevnik` v plánu, viz PC_zpevnik_sprava.md bod 4) —
existující, nebo nový: kolize kódu se tam NEODMÍTÁ, ale řeší automaticky —
kód z PDF se použije, pokud je v cílovém zpěvníku volný, jinak píseň dostane
další volný kód (`_priradit_kod_v_cili`) a přeřazení se vrátí v
`prejmenovani_kodu` (pro souhrn importu, "312 → 745: …").

Kategorie (rozdělení podle první číslice kódu, `kategorie` v plánu) jsou
oproti tomu pořád přísné: kolize se tam ODMÍTÁ (celý import se zastaví, nic
se nezaloží) — jsou to vedlejší, sdílené zpěvníky napříč více importy, kde
tiché přečíslování by matlo případné jiné odkazy na tenhle kód. Druhé
spuštění stejného plánu do STEJNÉ kategorie tak nikdy nevyrobí duplicitní
čísla, jen se zastaví s jasnou chybou.

POZOR — idempotence písní samotných (ne kódů): tahle funkce NEDETEKUJE, že
konkrétní píseň už byla naimportovaná dřív (žádné srovnání podle názvu ani
obsahu) — `Pisen.objects.create` se volá pro každou položku plánu vždycky.
Import stejného PDF do stejného CÍLOVÉHO zpěvníku podruhé proto založí
DUPLICITNÍ písně (pod novými kódy, díky remapu výš) — na rozdíl od
kategorií tenhle target už žádnou pojistku nemá. Viz report k
PC_zpevnik_sprava.md bodu 4 pro návrh řešení (nezavedeno v týhle úpravě).
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
          "cely_zpevnik": {"existujici_id": Zpevnik | None, "nazev": str},
        }

    `kategorie` vyrábí PRO PROHLÍŽENÍ podle první číslice kódu — vlastní
    Slozka + Zpevnik na kategorii, protože Slozka sama o sobě písně držet
    neumí (jen Zpevnik). `cely_zpevnik` je POVINNÝ cíl importu (bod 4) —
    existující zpěvník (`existujici_id`, po projití serializerem už je to
    rovnou Zpevnik instance), nebo nový (`nazev`). Píseň může být v obou
    (kategorii i cíli) zároveň (M2M), takže se tím nic neztrácí.

    Vrací dict {"pisne": [Pisen, ...], "slozky": [Slozka, ...], "zpevniky":
    [Zpevnik, ...], "kod_podle_pisne": {pisen_id: kod_v_cili},
    "prejmenovani_kodu": [{"puvodni", "novy", "nazev"}, ...]}.
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
                cislo=pisen.dalsi_cislo_verze(),
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

        # --- CÍLOVÝ zpěvník (bod 4) — existující, nebo nový; kolize kódu se
        # tady NEODMÍTÁ, ale řeší automaticky (viz modul docstring). ---
        existujici = cely_zpevnik_plan.get("existujici_id")
        cil_zpevnik = existujici or Zpevnik.objects.create(nazev=cely_zpevnik_plan["nazev"])

        # Rezervovaná množina pro "další volný kód" musí od začátku obsahovat
        # VŠECHNY kódy zadané v týhle dávce (ne jen ty, co se ukážou po
        # kolizi) — jinak by náhradní kód pro jednu píseň mohl sebrat kód,
        # který si legitimně (bez kolize) žádá jiná píseň dál v plánu.
        obsazene_existujici = set(cil_zpevnik.polozky.values_list("kod", flat=True))
        vsechny_zadane_kody = {kod_podle_pisne[p.id] for p in vytvorene_pisne}
        rezervovane = obsazene_existujici | vsechny_zadane_kody

        prejmenovani_kodu = []
        kod_v_cili_podle_pisne = {}
        for p in vytvorene_pisne:
            puvodni_kod = kod_podle_pisne[p.id]
            if puvodni_kod in obsazene_existujici:
                novy_kod = _dalsi_volny_kod(rezervovane)
                rezervovane.add(novy_kod)
                prejmenovani_kodu.append(
                    {"puvodni": puvodni_kod, "novy": novy_kod, "nazev": p.nazev}
                )
            else:
                novy_kod = puvodni_kod
            kod_v_cili_podle_pisne[p.id] = novy_kod
            PolozkaZpevniku.objects.create(zpevnik=cil_zpevnik, pisen=p, kod=novy_kod)
        vytvorene_zpevniky.append(cil_zpevnik)

    return {
        "pisne": vytvorene_pisne,
        "slozky": vytvorene_slozky,
        "zpevniky": vytvorene_zpevniky,
        # Skutečné kódy V CÍLOVÉM zpěvníku (po případném přeřazení) — pro
        # odpověď API. Kategorie si nesou svoje původní kódy z `kod_podle_pisne`
        # nezávisle (viz smyčka výš), tenhle dict je jen pro "pisne" v odpovědi.
        "kod_podle_pisne": kod_v_cili_podle_pisne,
        "prejmenovani_kodu": prejmenovani_kodu,
    }


def _dalsi_volny_kod(obsazene):
    """Stejná politika jako ZpevnikViewSet.dalsi_kod — max + 1 (ne první
    volná mezera), 101 pro prázdný zpěvník."""
    kandidat = (max(obsazene) + 1) if obsazene else 101
    while kandidat in obsazene:
        kandidat += 1
    return kandidat


def _zkontroluj_plan(pisne_plan, pocet_stran, kategorie_plan, cely_zpevnik_plan):
    if not pisne_plan:
        raise ValidationError({"pisne": ["Plán neobsahuje žádnou píseň."]})

    if not cely_zpevnik_plan.get("existujici_id"):
        nazev = cely_zpevnik_plan.get("nazev")
        if nazev and Zpevnik.objects.filter(nazev=nazev).exists():
            raise ValidationError(
                {
                    "cely_zpevnik": [
                        f"Zpěvník „{nazev}“ už existuje — vyber ho jako existující cíl, "
                        "ne nový."
                    ]
                }
            )

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

    # Kolize s DB — jen pro KATEGORIE (odmítnutí celého importu, viz modul
    # docstring): kontroluje se proti zpěvníkům, které tenhle import osloví
    # jménem A které DB už obsahuje. Nově založený zpěvník je prázdný, tam
    # kolidovat není s čím. CÍLOVÝ zpěvník (`cely_zpevnik`) tu schválně NENÍ
    # — jeho kolize se řeší přeřazením kódu v `proved_import`, ne odmítnutím.
    cilove_nazvy = {
        kat["nazev"] for kat in kategorie_plan if kat.get("vytvorit", True)
    }

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
