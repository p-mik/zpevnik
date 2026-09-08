from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from zpevnik.api_views import (
    PisenViewSet,
    PolozkaSetlistuViewSet,
    SetlistViewSet,
    SlozkaViewSet,
    VerejnySouborView,
    VerejnyZpevnikView,
    VerzePisneViewSet,
    ZpevnikViewSet,
    auth_login,
    auth_logout,
    auth_me,
)
from zpevnik.views import index

router = DefaultRouter()
router.register("pisne", PisenViewSet, basename="pisen")
router.register("verze-pisni", VerzePisneViewSet, basename="verzepisne")
router.register("slozky", SlozkaViewSet, basename="slozka")
router.register("zpevniky", ZpevnikViewSet, basename="zpevnik")
router.register("setlisty", SetlistViewSet, basename="setlist")
router.register("polozky-setlistu", PolozkaSetlistuViewSet, basename="polozkasetlistu")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", auth_login, name="auth-login"),
    path("api/auth/logout/", auth_logout, name="auth-logout"),
    path("api/auth/me/", auth_me, name="auth-me"),
    path("api/verejny/<str:token>/", VerejnyZpevnikView.as_view(), name="verejny-zpevnik"),
    path(
        "api/verejny/<str:token>/pisen/<int:kod>/soubor/",
        VerejnySouborView.as_view(),
        name="verejny-soubor",
    ),
    path("api/", include(router.urls)),
    path("", index, name="index"),
]

# ZÁMĚRNĚ TU NENÍ static(MEDIA_URL, ...) ani jiné servírování /media/.
# Každý soubor musí projít kontrolou práv (viz zpevnik/soubory.py) — jakákoliv
# přímá cesta k media složce (i "jen pro DEBUG") ten mechanismus obchází.
# Ze stejného důvodu nesmí v nginx vhostu vzniknout `location /media/`.
