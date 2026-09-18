import json

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

from .import_pisni import proved_import
from .models import (
    Anotace,
    Pisen,
    PolozkaSetlistu,
    PolozkaZpevniku,
    Setlist,
    Slozka,
    VerzePisne,
    Zpevnik,
)
from .permissions import IsStaffOrReadOnly, VerzePisnePermission
from .soubory import odpoved_se_souborem, smi_cist_verzi
from .serializers import (
    AnotaceSerializer,
    ImportPlanSerializer,
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
    """Plochý seznam napříč VŠEMI zpěvníky — bez `kod` filtru/řazení: kód je
    od fáze 2b vlastnost zařazení do konkrétního zpěvníku (viz
    PolozkaZpevniku), ne písně, takže tady žádné jednoznačné číslo není.
    Hledání/procházení podle kódu patří na zpěvníkem SCOPENÝ pohled
    (ZpevnikSerializer.pisne), ne sem."""

    permission_classes = [IsStaffOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nazev", "interpret"]
    ordering_fields = ["nazev"]
    ordering = ["nazev"]

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
        if not user.is_staff:
            # Člen smí vytvořit jen vlastní 'personal' verzi — server přepíše,
            # co by případně poslal v těle požadavku.
            serializer.save(stav=VerzePisne.STAV_PERSONAL, vlastnik=user)
            return
        # Admin smí vytvořit libovolný stav, ale osobní verze musí mít majitele:
        # `vlastnik` je v serializeru read-only, takže by jinak vznikla osobní
        # verze bez vlastníka — tu by si nenačetl ani její autor, protože
        # Pisen.aktivni_verze() páruje osobní verze právě přes vlastnika.
        extra = {}
        if serializer.validated_data.get("stav") == VerzePisne.STAV_PERSONAL:
            extra["vlastnik"] = user
        serializer.save(**extra)

    def perform_update(self, serializer):
        user = self.request.user
        if not user.is_staff:
            serializer.save(stav=VerzePisne.STAV_PERSONAL, vlastnik=user)
            return
        # Doplnit vlastníka jen tam, kde žádný není — jinak by admin úpravou
        # cizí osobní verze převzal její vlastnictví.
        extra = {}
        novy_stav = serializer.validated_data.get("stav", serializer.instance.stav)
        if novy_stav == VerzePisne.STAV_PERSONAL and serializer.instance.vlastnik_id is None:
            extra["vlastnik"] = user
        serializer.save(**extra)

    @action(detail=True, methods=["get", "put"], url_path="anotace")
    def anotace(self, request, pk=None):
        """MOJE poznámky k téhle verzi (fáze 2a).

        Anotace jsou osobní: dotaz je vždy zúžený na `request.user`, takže ani
        admin se přes tenhle endpoint k cizím poznámkám nedostane — u cizí
        verze dostane prostě svoje (zatím prázdné), ne cizí.

        Vážou se na konkrétní VerzePisne, ne na píseň: pozice platí nad
        konkrétním PDF, na jiné verzi by seděly jinde.

        PUT ukládá celé pole naráz. Autor je jeden, souběžná editace ze dvou
        zařízení se neřeší — poslední zápis vyhrává.
        """
        verze = get_object_or_404(VerzePisne, pk=pk)
        if not smi_cist_verzi(request.user, verze):
            # 404 stejně jako u souboru: o cizí personal verzi se nemá dozvědět
            # ani to, že existuje.
            raise Http404("Verze nenalezena.")

        if request.method == "GET":
            # Čtení nesmí zakládat řádek: čtečka se ptá při každém otevření
            # písně, takže by pouhé prolistování zpěvníku vyrobilo prázdnou
            # anotaci ke každé verzi.
            anotace = Anotace.objects.filter(
                verze_pisne=verze, vlastnik=request.user
            ).first()
            if anotace is None:
                return Response({"data": [], "upraveno": None})
            return Response(AnotaceSerializer(anotace).data)

        anotace, _ = Anotace.objects.get_or_create(
            verze_pisne=verze, vlastnik=request.user
        )
        serializer = AnotaceSerializer(anotace, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

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
        return Zpevnik.objects.select_related("slozka").prefetch_related("polozky__pisen")


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
            Zpevnik.objects.prefetch_related("polozky__pisen__verze"),
            verejny_token=token,
        )
        serializer = VerejnyZpevnikSerializer(
            zpevnik, context={"request": request, "verejny_token": token}
        )
        return Response(serializer.data)


class VerejnySouborView(APIView):
    """Soubor z veřejného zpěvníku — autorizuje token v URL, ne přihlášení.

    Řetěz oprávnění (každý článek musí projít):
      1. token -> právě jeden zpěvník (neplatný/odvolaný token = 404),
      2. píseň s tímhle kódem musí existovat V TOMHLE zpěvníku (kód je
         vlastnost zařazení do zpěvníku, PolozkaZpevniku — dotaz jde přes
         zpevnik.polozky, ne přes Pisen, ten už kód nemá),
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
        # Kontrola příslušnosti: hledá se jen mezi POLOŽKAMI tohoto zpěvníku
        # (kód platí jen v jeho rámci), ne globálně přes Pisen.
        polozka = get_object_or_404(
            PolozkaZpevniku.objects.select_related("pisen"), zpevnik=zpevnik, kod=kod
        )
        pisen = polozka.pisen

        verze = pisen.aktivni_verze(user=None)
        if verze is None or not verze.soubor:
            raise Http404("Píseň nemá veřejně dostupný soubor.")

        # Pás a šle: kdyby se logika výběru verze někdy změnila, ať to spadne
        # tady a ne až u uživatele.
        if verze.stav == VerzePisne.STAV_PERSONAL:
            raise Http404("Píseň nemá veřejně dostupný soubor.")

        return odpoved_se_souborem(verze)


class ImportView(APIView):
    """Hromadný import zpěvníku z jednoho PDF — jen admin (fáze 1e).

    Parsování (hledání kódu/názvu/interpreta v hlavičce stránky) proběhlo na
    klientovi přes PDF.js — sem přichází jen POTVRZENÝ plán, který si
    uživatel prošel a opravil v kontrolní tabulce. Server sám nic neparsuje,
    jen ověří tvar plánu a fyzicky rozřeže PDF (viz zpevnik/import_pisni.py).
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        soubor = request.FILES.get("soubor")
        if not soubor:
            return Response(
                {"soubor": ["Soubor je povinný."]}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            plan_data = json.loads(request.data.get("plan", ""))
        except (TypeError, ValueError):
            return Response(
                {"plan": ["Plán není platné JSON."]}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ImportPlanSerializer(data=plan_data)
        serializer.is_valid(raise_exception=True)

        vysledek = proved_import(soubor, serializer.validated_data)
        kod_podle_pisne = vysledek["kod_podle_pisne"]

        return Response(
            {
                "pisne": [
                    {"id": p.id, "kod": kod_podle_pisne[p.id], "nazev": p.nazev}
                    for p in vysledek["pisne"]
                ],
                "slozky": [s.nazev for s in vysledek["slozky"]],
                "zpevniky": [z.nazev for z in vysledek["zpevniky"]],
            },
            status=status.HTTP_201_CREATED,
        )


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
