# Zapíná unikátnost (pisen, cislo) AŽ PO backfillu v 0010 — kdyby šla
# před ním, spadne na existujících řádcích (všechny NULL, ale Postgres
# bere NULL jako různé hodnoty, takže by to samo o sobě neselhalo; pořadí
# je tu spíš o významu: constraint dává smysl až s daty, která má hlídat).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zpevnik', '0010_priradit_cislo_verzim'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='verzepisne',
            constraint=models.UniqueConstraint(fields=('pisen', 'cislo'), name='unikatni_cislo_verze_pisne'),
        ),
    ]
