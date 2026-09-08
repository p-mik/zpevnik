from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from zpevnik.api_views import (
    PisenViewSet,
    PolozkaSetlistuViewSet,
    SetlistViewSet,
    SlozkaViewSet,
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
    path("api/", include(router.urls)),
    path("", index, name="index"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
