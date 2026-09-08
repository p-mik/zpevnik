"""Úklid osiřelých PDF v media složce.

Proč to existuje: mazání verze písně soubor na disku ZÁMĚRNĚ nemaže (viz README,
sekce o mazání souborů). Osiřelé soubory by se ale samy neuklidily nikdy, tak je
na to tenhle příkaz — pouští se ručně nebo z cronu, s odstupem několika dnů,
aby překlep v adminu šel ještě vzít zpět.

Bez `--smazat` jen vypíše, co by smazal.
"""

import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from zpevnik.models import VerzePisne

PODSLOZKA = "verze"


class Command(BaseCommand):
    help = "Vypíše (a s --smazat smaže) soubory v media, na které neukazuje žádná verze písně."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dny",
            type=int,
            default=30,
            help="Nechat na pokoji soubory mladší než N dnů (výchozí 30).",
        )
        parser.add_argument(
            "--smazat",
            action="store_true",
            help="Opravdu mazat. Bez tohoto přepínače jde jen o výpis.",
        )

    def handle(self, *args, **options):
        dny = options["dny"]
        smazat = options["smazat"]

        koren = os.path.join(settings.MEDIA_ROOT, PODSLOZKA)
        if not os.path.isdir(koren):
            self.stdout.write("Složka s verzemi zatím neexistuje, není co uklízet.")
            return

        # Cesty, na které ukazuje DB. Bereme .name (relativní cesta), ne .path.
        pouzivane = set(
            VerzePisne.objects.exclude(soubor="")
            .exclude(soubor__isnull=True)
            .values_list("soubor", flat=True)
        )

        hranice = time.time() - dny * 86400
        osirele, uvolneno, preskoceno = [], 0, 0

        for slozka, _, soubory in os.walk(koren):
            for jmeno in soubory:
                absolutni = os.path.join(slozka, jmeno)
                relativni = os.path.relpath(absolutni, settings.MEDIA_ROOT).replace(
                    os.sep, "/"
                )
                if relativni in pouzivane:
                    continue
                if os.path.getmtime(absolutni) > hranice:
                    preskoceno += 1
                    continue
                osirele.append((absolutni, relativni, os.path.getsize(absolutni)))

        for absolutni, relativni, velikost in osirele:
            uvolneno += velikost
            if smazat:
                os.remove(absolutni)
                self.stdout.write(f"smazáno: {relativni}")
            else:
                self.stdout.write(f"osiřelé: {relativni}")

        if smazat:
            self._smaz_prazdne_slozky(koren)

        shrnuti = (
            f"Osiřelých souborů: {len(osirele)} ({uvolneno / 1024:.0f} kB), "
            f"mladších než {dny} dnů přeskočeno: {preskoceno}."
        )
        if osirele and not smazat:
            shrnuti += " Spusť s --smazat, ať se opravdu smažou."
        self.stdout.write(self.style.SUCCESS(shrnuti))

    def _smaz_prazdne_slozky(self, koren):
        for slozka, _, _ in sorted(os.walk(koren), reverse=True):
            if slozka != koren and not os.listdir(slozka):
                os.rmdir(slozka)
