from django.apps import AppConfig
from django.core.checks import Error, register


class ZpevnikConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "zpevnik"
    verbose_name = "Zpěvník"

    def ready(self):
        register(zkontroluj_servirovani_souboru)


def zkontroluj_servirovani_souboru(app_configs, **kwargs):
    """V produkci nesmí Django streamovat soubory samo — od toho je nginx.

    Nouzový režim (X_ACCEL_REDIRECT=False) je jen pro lokální vývoj. Kdyby se
    zapnul v produkci, servírovaly by se noty přes gunicorn worker a tichý
    výkonnostní problém by nikdo nenašel — tak ať to spadne nahlas.

    Váže se na ENVIRONMENT, ne na DEBUG — Django test runner DEBUG vždy
    vynutí na False, takže by tahle kontrola vyskakovala i při obyčejném
    `manage.py test` v lokálním vývoji s X_ACCEL_REDIRECT=False (přesně tak,
    jak to README doporučuje bez nginx). ENVIRONMENT default je "production",
    takže zapomenuté nastavení proměnné v produkci kontrolu neztiší.
    """
    from django.conf import settings

    if settings.ENVIRONMENT == "production" and not settings.X_ACCEL_REDIRECT:
        return [
            Error(
                "X_ACCEL_REDIRECT je vypnutý v produkčním prostředí (ENVIRONMENT=production).",
                hint="V produkci nastav X_ACCEL_REDIRECT=True — soubory musí "
                "posílat nginx přes X-Accel-Redirect, ne Django.",
                id="zpevnik.E001",
            )
        ]
    return []
