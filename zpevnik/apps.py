from django.apps import AppConfig
from django.core.checks import Error, register


class ZpevnikConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "zpevnik"
    verbose_name = "Zpěvník"

    def ready(self):
        register(zkontroluj_servirovani_souboru)


def zkontroluj_servirovani_souboru(app_configs, **kwargs):
    """Bez DEBUGu nesmí Django streamovat soubory samo — od toho je nginx.

    Nouzový režim (X_ACCEL_REDIRECT=False) je jen pro lokální vývoj. Kdyby se
    zapnul v produkci, servírovaly by se noty přes gunicorn worker a tichý
    výkonnostní problém by nikdo nenašel — tak ať to spadne nahlas.
    """
    from django.conf import settings

    if not settings.DEBUG and not settings.X_ACCEL_REDIRECT:
        return [
            Error(
                "X_ACCEL_REDIRECT je vypnutý, ale DEBUG je False.",
                hint="V produkci nastav X_ACCEL_REDIRECT=True — soubory musí "
                "posílat nginx přes X-Accel-Redirect, ne Django.",
                id="zpevnik.E001",
            )
        ]
    return []
