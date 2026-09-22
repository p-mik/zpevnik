# Doplní `cislo` existujícím verzím podle pořadí `id` V RÁMCI KAŽDÉ PÍSNĚ
# (viz PC_zpevnik_akordovy_zapis_upravy.md, bod 5) — první nahraná verze
# dostane 1, druhá 2 atd. `id` je jediné dostupné pořadí: `vytvoreno` by u
# starých řádků mohlo teoreticky kolidovat (import v jedné transakci), `id`
# ne.

from django.db import migrations


def priradit_cislo(apps, schema_editor):
    VerzePisne = apps.get_model("zpevnik", "VerzePisne")
    Pisen = apps.get_model("zpevnik", "Pisen")
    for pisen_id in Pisen.objects.values_list("id", flat=True):
        verze = VerzePisne.objects.filter(pisen_id=pisen_id).order_by("id")
        for cislo, verze_id in enumerate(verze.values_list("id", flat=True), start=1):
            VerzePisne.objects.filter(id=verze_id).update(cislo=cislo)


def smazat_cislo(apps, schema_editor):
    VerzePisne = apps.get_model("zpevnik", "VerzePisne")
    VerzePisne.objects.update(cislo=None)


class Migration(migrations.Migration):

    dependencies = [
        ('zpevnik', '0009_verzepisne_cislo'),
    ]

    operations = [
        migrations.RunPython(priradit_cislo, smazat_cislo),
    ]
