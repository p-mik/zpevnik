from django.contrib.auth import authenticate, login, logout
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pisen, PolozkaSetlistu, Setlist, Slozka, VerzePisne, Zpevnik
from .permissions import IsStaffOrReadOnly, VerzePisnePermission
from .soubory import odpoved_se_souborem, smi_cist_verzi
from .serializers import (
    PisenDetailSerializer,
    PisenListSerializer,
    PolozkaSetlistuSerializer,
    SetlistSerializer,
    SlozkaSerializer,
    UserSerializer,
    VerejnyZpevnikSerializer,
    VerzePisneSerializer,
    ZpevnikSerializer,
)


class PisenViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["kod"]
    search_fields = ["nazev", "interpret"]
    ordering_fields = ["kod", "nazev"]
    ordering = ["kod"]

    def get_queryset(self):
        if self.action == "retrieve":
            return Pisen.objects.prefetch_related("verze", "verze__vlastnik")
        return Pisen.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return PisenListSerializer
        return PisenDetailSerializer


class VerzePisneViewSet(viewsets.ModelViewSet):
    serializer_class = VerzePisneSerializer
    permission_classes = [VerzePisnePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["pisen", "stav", "vlastnik"]

    def get_queryset(self):
        return VerzePisne.objects.select_related("pisen", "vlastnik")

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_staff:
            serializer.save()
        else:
            # Člen smí vytvořit jen vlastní 'personal' verzi — server přepíše,
            # co by případně poslal v těle požadavku.
            serializer.save(stav=VerzePisne.STAV_PERSONAL, vlastnik=user)

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_staff:
            serializer.save()
        else:
            serializer.save(stav=VerzePisne.STAV_PERSONAL, vlastnik=user)

    @action(detail=True, methods=["get"], url_path="soubor")
    def soubor(self, request, pk=None):
        """PDF verze — práva se ověří tady, soubor pak pošle nginx."""
        verze = get_object_or_404(VerzePisne, pk=pk)
        if not smi_cist_verzi(request.user, verze):
            # 404 místo 403 schválně: cizí personal verze nemá dát ani vědět,
            # že existuje.
            raise Http404("Verze nenalezena.")
        return odpoved_se_souborem(verze)


class SlozkaViewSet(viewsets.ModelViewSet):
    queryset = Slozka.objects.all()
    serializer_class = SlozkaSerializer
    permission_classes = [IsStaffOrReadOnly]


class ZpevnikViewSet(viewsets.ModelViewSet):
    serializer_class = ZpevnikSerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        return Zpevnik.objects.select_related("slozka").prefetch_related("pisne")


class SetlistViewSet(viewsets.ModelViewSet):
    """Setlisty jsou sdílený zdroj kapely — libovolný přihlášený člen je smí
    vytvářet/upravovat/mazat (model nemá pole vlastnictví, viz README)."""

    serializer_class = SetlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Setlist.objects.prefetch_related("polozky", "polozky__pisen")


class PolozkaSetlistuViewSet(viewsets.ModelViewSet):
    queryset = PolozkaSetlistu.objects.select_related("setlist", "pisen")
    serializer_class = PolozkaSetlistuSerializer
    permission_classes = [permissions.IsAuthenticated]


class VerejnyZpevnikView(APIView):
    """Neautentizovaný, read-only přístup ke zpěvníku přes neuhodnutelný token."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        zpevnik = get_object_or_404(
            Zpevnik.objects.prefetch_related("pisne__verze"), verejny_token=token
        )
        serializer = VerejnyZpevnikSerializer(
            zpevnik, context={"request": request, "verejny_token": token}
        )
        return Response(serializer.data)


class VerejnySouborView(APIView):
    """Soubor z veřejného zpěvníku — autorizuje token v URL, ne přihlášení.

    Řetěz oprávnění (každý článek musí projít):
      1. token -> právě jeden zpěvník (neplatný/odvolaný token = 404),
      2. píseň musí být v TOMHLE zpěvníku (dotaz jde přes zpevnik.pisne),
      3. verzi vybírá server přes aktivni_verze(user=None), která z principu
         nikdy nevrátí personal verzi — klient číslo verze vůbec neposílá.

    Klíčové je právě to, že se v URL neuvádí ID verze: kdyby ho posílal klient,
    stačilo by uhodnout ID cizí personal verze u písně, která ve veřejném
    zpěvníku je. Takhle je adresovatelné jen "píseň X v zpěvníku Y" a co se
    z toho pošle, rozhoduje server.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token, kod):
        if not token:
            raise Http404("Neplatný token.")

        zpevnik = get_object_or_404(Zpevnik, verejny_token=token)
        # Kontrola příslušnosti: hledá se jen mezi písněmi tohoto zpěvníku.
        pisen = get_object_or_404(zpevnik.pisne, kod=kod)

        verze = pisen.aktivni_verze(user=None)
        if verze is None or not verze.soubor:
            raise Http404("Píseň nemá veřejně dostupný soubor.")

        # Pás a šle: kdyby se logika výběru verze někdy změnila, ať to spadne
        # tady a ne až u uživatele.
        if verze.stav == VerzePisne.STAV_PERSONAL:
            raise Http404("Píseň nemá veřejně dostupný soubor.")

        return odpoved_se_souborem(verze)


# --- Auth (standardní Django session login, Google OAuth přijde později) ---


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"authenticated": False})
        data = UserSerializer(request.user).data
        data["authenticated"] = True
        data["role"] = "admin" if request.user.is_staff else "clen"
        return Response(data)


auth_me = MeView.as_view()


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_login(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Neplatné přihlašovací údaje."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    login(request, user)
    data = UserSerializer(user).data
    data["authenticated"] = True
    data["role"] = "admin" if user.is_staff else "clen"
    return Response(data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def auth_logout(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)
