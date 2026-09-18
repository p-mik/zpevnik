# Krok 3/3: teď, když jsou data bezpečně zkopírovaná v PolozkaZpevniku
# (0006), přepnout Zpevnik.pisne na `through=PolozkaZpevniku` a zrušit
# Pisen.kod — kód je od teď vlastností zařazení do zpěvníku, ne písně.
#
# Zpevnik.pisne jde přepnout na `through=` jen přes RemoveField+AddField, ne
# AlterField — Django to na M2M poli přímo neumí ("cannot alter to or from
# M2M fields, or add or remove through="). RemoveField smaže starou
# automatickou spojovací tabulku (0006 už z ní data bezpečně obratem
# přenesla), AddField s `through=` pak jen zaregistruje pole na JIŽ
# existující PolozkaZpevniku, žádnou novou tabulku nezakládá.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zpevnik", "0006_zkopiruj_kody_do_polozek"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="pisen",
            options={
                "ordering": ["nazev"],
                "verbose_name": "Píseň",
                "verbose_name_plural": "Písně",
            },
        ),
        migrations.RemoveField(
            model_name="pisen",
            name="kod",
        ),
        migrations.RemoveField(
            model_name="zpevnik",
            name="pisne",
        ),
        migrations.AddField(
            model_name="zpevnik",
            name="pisne",
            field=models.ManyToManyField(
                blank=True,
                related_name="zpevniky",
                through="zpevnik.PolozkaZpevniku",
                to="zpevnik.pisen",
            ),
        ),
    ]
