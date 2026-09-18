# Krok 2/3: DATOVÁ migrace. Zkopíruje současné (zpevnik, píseň) vazby ze
# staré automatické M2M tabulky do nové PolozkaZpevniku, s kódem vzatým z
# Pisen.kod — ten v tomhle kroku ještě existuje (RemoveField je až v 0007).
# Bez tohohle kroku by krok 3 (přepnutí Zpevnik.pisne na `through=`)
# všechny existující vazby jen tiše ztratil.

from django.db import migrations


def zkopiruj(apps, schema_editor):
    Zpevnik = apps.get_model("zpevnik", "Zpevnik")
    Pisen = apps.get_model("zpevnik", "Pisen")
    PolozkaZpevniku = apps.get_model("zpevnik", "PolozkaZpevniku")

    # `.through` = pořád ještě automaticky vygenerovaná M2M tabulka v tomhle
    # bodě historie migrací (AlterField na `through=PolozkaZpevniku` proběhne
    # až v 0007) — má jen zpevnik_id/pisen_id, žádný kód.
    stara_vazba = Zpevnik.pisne.through
    kody = dict(Pisen.objects.values_list("id", "kod"))

    nove = [
        PolozkaZpevniku(zpevnik_id=v.zpevnik_id, pisen_id=v.pisen_id, kod=kody[v.pisen_id])
        for v in stara_vazba.objects.all()
    ]
    PolozkaZpevniku.objects.bulk_create(nove)


def smaz_zkopirovane(apps, schema_editor):
    # Reverzní krok jen pro `migrate zpevnik <dřívější>` (rollback) — maže
    # přesně to, co `zkopiruj` vytvořil, ať jde migrace i zpátky.
    PolozkaZpevniku = apps.get_model("zpevnik", "PolozkaZpevniku")
    PolozkaZpevniku.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("zpevnik", "0005_polozkazpevniku"),
    ]

    operations = [
        migrations.RunPython(zkopiruj, smaz_zkopirovane),
    ]
