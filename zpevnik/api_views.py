import json

from django.contrib.auth import authenticate, login, logout
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .akordy_pdf import vygeneruj_pdf
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
from .soubory import naplanuj_smazani_souboru, odpoved_se_souborem, smi_cist_verzi
from .serializers import (
    AkordovyZapisSerializer,
    AnotaceSerializer,
    ImportPlanSerializer,
    PisenDetailSerializer,
    PisenListSerializer,
    PisenVZpevnikuSerializer,
    PolozkaSetlistuSerializer,
    PridatPisenSerializer,
    SetlistSerializer,
    SlozkaSerializer,
    UserSerializer,
    VerejnyZpevnikSerializer,
    VerzePisneSerializer,
    ZpevnikSerializer,
)

# Prázdný akordový zápis — výchozí tělo pro PisenViewSet.verze_akordy, když
# klient nepošle žádné (viz PC_zpevnik_akordovy_zapis.md: "prázdná, nebo s
# tělem JSON"). 4/4 je nejběžnější výchozí takt, editor (fáze 2) ho může
# hned přepnout.
PRAZDNY_AKORDOVY_ZAPIS = {"schema": 2, "takt": {"dob": 4, "hodnota": 4}, "tempo": None, "sekce": []}


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

    @action(detail=True, methods=["get"], url_path="smazat-nahled")
    def smazat_nahled(self, request, pk=None):
        """Náhled pro potvrzovací dialog "Smazat píseň" (PC_zpevnik_sprava.md
        bod 5) — jen čte, nic nemaže. `IsStaffOrReadOnly` dovolí GET komukoli
        přihlášenému, ale tlačítko v UI se zobrazuje jen adminovi (mazání
        samotné je přes DELETE stejně admin-only, viz `perform_destroy`)."""
        pisen = self.get_object()
        pocet_anotaci = Anotace.objects.filter(
            Q(pisen=pisen) | Q(verze_pisne__pisen=pisen)
        ).count()
        return Response(
            {
                "verzi": pisen.verze.count(),
                "anotaci": pocet_anotaci,
                "zpevniky": list(pisen.zpevniky.values_list("nazev", flat=True)),
                "setlisty": pisen.setlisty.count(),
            }
        )

    def perform_destroy(self, instance):
        # Soubory na disku se u týhle explicitní, potvrzené admin akce
        # (na rozdíl od běžného mazání verze, viz naplanuj_smazani_souboru)
        # OPRAVDU mažou — ale až po úspěšném commitu, ať rollback nenechá
        # záznamy bez souborů.
        soubory = [
            (v.soubor.storage, v.soubor.name) for v in instance.verze.all() if v.soubor
        ]
        with transaction.atomic():
            instance.delete()
        naplanuj_smazani_souboru(soubory)

    @action(
        detail=True,
        methods=["post"],
        url_path="verze-akordy",
        permission_classes=[permissions.IsAuthenticated],
    )
    def verze_akordy(self, request, pk=None):
        """Nová verze se `zdroj=akordy` — prázdná, nebo rovnou s tělem JSON
        (`{"akordy": {...}}`, viz AkordovyZapisSerializer). Vždycky osobní
        koncept, stejně jako anotace: stav i vlastník si appka dosadí sama,
        klient je poslat nemůže — libovolný přihlášený člen tak smí založit
        vlastní akordovou verzi, aniž by z ní udělal rovnou "potvrzenou".

        PDF se generuje rovnou při vytvoření (ne až při prvním uložení), ať
        je verze hned použitelná ve čtečce/stage módu (viz akordy_pdf.py).
        """
        pisen = self.get_object()

        vstup = (request.data or {}).get("akordy") or PRAZDNY_AKORDOVY_ZAPIS
        serializer = AkordovyZapisSerializer(data=vstup)
        serializer.is_valid(raise_exception=True)

        pdf_bytes = vygeneruj_pdf(pisen, serializer.validated_data)
        verze = VerzePisne.objects.create(
            pisen=pisen,
            cislo=pisen.dalsi_cislo_verze(),
            typ_obsahu=VerzePisne.TYP_PDF,
            zdroj=VerzePisne.ZDROJ_AKORDY,
            akordy=serializer.validated_data,
            stav=VerzePisne.STAV_PERSONAL,
            vlastnik=request.user,
        )
        verze.soubor.save(f"akordy-{verze.pk}.pdf", ContentFile(pdf_bytes), save=True)

        return Response(
            VerzePisneSerializer(verze, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class VerzePisneViewSet(viewsets.ModelViewSet):
    serializer_class = VerzePisneSerializer
    permission_classes = [VerzePisnePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["pisen", "stav", "vlastnik"]

    def get_queryset(self):
        return VerzePisne.objects.select_related("pisen", "vlastnik")

    def perform_create(self, serializer):
        user = self.request.user
        # Číslo verze přiděluje výhradně server (viz VerzePisne.cislo) —
        # `pisen` je v tuhle chvíli vždycky ve validated_data (povinné pole).
        cislo = serializer.validated_data["pisen"].dalsi_cislo_verze()
        if not user.is_staff:
            # Člen smí vytvořit jen vlastní 'personal' verzi — server přepíše,
            # co by případně poslal v těle požadavku.
            serializer.save(stav=VerzePisne.STAV_PERSONAL, vlastnik=user, cislo=cislo)
            return
        # Admin smí vytvořit libovolný stav, ale osobní verze musí mít majitele:
        # `vlastnik` je v serializeru read-only, takže by jinak vznikla osobní
        # verze bez vlastníka — tu by si nenačetl ani její autor, protože
        # Pisen.aktivni_verze() páruje osobní verze právě přes vlastnika.
        extra = {"cislo": cislo}
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

    @action(detail=True, methods=["get", "put"], url_path="akordy")
    def akordy(self, request, pk=None):
        """Zdrojová data akordového zápisu (viz PC_zpevnik_akordovy_zapis.md
        a AkordovyZapisSerializer). Jen u `zdroj=akordy` — na PDF verzi
        (nahrané nebo z importu) `/akordy/` nedává smysl, proto 404 stejně
        jako u cizí `personal` verze (viz `soubor`/`anotace` výš — stejná
        4-4-4 logika viditelnosti).

        PUT SYNCHRONNĚ přegeneruje `soubor` (viz akordy_pdf.vygeneruj_pdf) —
        čtečka, stage mode i anotace dál pracují jen se souborem, o
        existenci akordového zápisu nemusí vůbec vědět. Anotace jsou ale ve
        zlomcích STRÁNKY — když se PDF přeskládá, mohou ujet, proto se v
        odpovědi vrací i jejich počet (hlášku uživateli ukazuje editor,
        fáze 2, ne API samo).
        """
        verze = get_object_or_404(VerzePisne.objects.select_related("pisen"), pk=pk)
        if not smi_cist_verzi(request.user, verze):
            raise Http404("Verze nenalezena.")
        if verze.zdroj != VerzePisne.ZDROJ_AKORDY:
            raise Http404("Tahle verze nemá akordový zápis.")

        if request.method == "GET":
            return Response(verze.akordy or {})

        # PUT — zápis: get_object_or_404 výš obchází DRF get_object(), takže
        # has_object_permission se sám nezavolá; VerzePisnePermission dá
        # admin cokoliv, člena jen na jeho vlastní personal verzi.
        self.check_object_permissions(request, verze)

        serializer = AkordovyZapisSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pdf_bytes = vygeneruj_pdf(verze.pisen, serializer.validated_data)
        verze.akordy = serializer.validated_data
        verze.soubor.save(f"akordy-{verze.pk}.pdf", ContentFile(pdf_bytes), save=False)
        verze.save(update_fields=["akordy", "soubor", "upraveno"])

        # Souhrnný počet napříč VŠEMI vlastníky (ne jen editující osoby) —
        # reflow může posunout poznámky komukoli, kdo je na týhle verzi má,
        # ne jen tomu, kdo zrovna ukládá. Vrací se jen počet, ne obsah ani
        # čí jsou — to soukromí poznámek neporušuje.
        pocet_anotaci = sum(
            len(a.data) for a in Anotace.objects.filter(verze_pisne=verze)
        )

        return Response(
            {"akordy": verze.akordy, "pocet_anotaci_ktere_mohly_ujet": pocet_anotaci}
        )

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

    def _vyhradni_pisne(self, zpevnik):
        """Písně, které jsou JEN v tomhle zpěvníku — ty se smažou spolu s
        ním (píseň bez zpěvníku nemá existovat, viz PC_zpevnik_sprava.md
        bod 5). `n=1` = přesně jedno zařazení celkem, a to je tohle.

        Kandidáty se filtrují podle PK (`id__in`), NE podle `zpevniky=` —
        filtr a `Count("zpevniky")` na STEJNÉM vztahu by sdílely jeden join
        a Count by tak vyšel vždycky 1 (počítal by jen řádek odpovídající
        filtru), i pro píseň se třemi zařazeními. Filtr po PK je nezávislý
        join, takže Count správně sečte VŠECHNA zařazení dané písně."""
        kandidati = Pisen.objects.filter(zpevniky=zpevnik).values_list("id", flat=True)
        return Pisen.objects.filter(id__in=list(kandidati)).annotate(n=Count("zpevniky")).filter(n=1)

    @action(detail=True, methods=["get"], url_path="smazat-nahled")
    def smazat_nahled(self, request, pk=None):
        """Náhled pro potvrzovací dialog "Smazat zpěvník" — jen čte."""
        zpevnik = self.get_object()
        vyhradni = self._vyhradni_pisne(zpevnik)
        pocet_vyhradnich = vyhradni.count()
        return Response(
            {
                "pisni_zmizi": pocet_vyhradnich,
                "pisni_zustane": zpevnik.polozky.count() - pocet_vyhradnich,
                "setlisty": Setlist.objects.filter(pisne__in=vyhradni).distinct().count(),
            }
        )

    def perform_destroy(self, instance):
        vyhradni = list(self._vyhradni_pisne(instance))
        soubory = [
            (v.soubor.storage, v.soubor.name)
            for p in vyhradni
            for v in p.verze.all()
            if v.soubor
        ]
        with transaction.atomic():
            # Zpěvník napřed — uvolní PolozkaZpevniku vazby, díky čemu jsou
            # "výhradní" písně po týhle chvíli opravdu bez jediného zařazení.
            instance.delete()
            Pisen.objects.filter(pk__in=[p.pk for p in vyhradni]).delete()
        naplanuj_smazani_souboru(soubory)

    @action(detail=True, methods=["get"], url_path="dalsi-kod")
    def dalsi_kod(self, request, pk=None):
        """Návrh dalšího volného kódu V TOMHLE zpěvníku — jen návrh pro
        předvyplnění formuláře (fáze 2). Skutečnou kolizi stejně ověří znovu
        `pridat_pisen` při zápisu, tenhle endpoint nic nezamyká ani nerezervuje.
        """
        zpevnik = self.get_object()
        maximum = zpevnik.polozky.aggregate(m=Max("kod"))["m"]
        navrh = 101 if maximum is None else maximum + 1
        return Response({"kod": navrh})

    @action(
        detail=True,
        methods=["post"],
        url_path="pridat-pisen",
        permission_classes=[permissions.IsAuthenticated],
    )
    def pridat_pisen(self, request, pk=None):
        """Zařadí existující píseň do TOHOHLE zpěvníku pod daným kódem —
        s kontrolou kolize (viz PolozkaZpevniku.unikatni_kod_ve_zpevniku).
        Stejně jako `verze_akordy` na PisenViewSet: libovolný přihlášený
        člen, ne jen admin — přidání JEDNÉ vlastní písně do zpěvníku je
        aditivní osobní akce, ne správa zpěvníku jako celku (tu dál hlídá
        IsStaffOrReadOnly na zbytku tohohle viewsetu)."""
        zpevnik = self.get_object()
        serializer = PridatPisenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pisen = serializer.validated_data["pisen"]
        kod = serializer.validated_data["kod"]

        if PolozkaZpevniku.objects.filter(zpevnik=zpevnik, kod=kod).exists():
            return Response(
                {"kod": [f"Kód {kod} je v tomhle zpěvníku už obsazený."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if PolozkaZpevniku.objects.filter(zpevnik=zpevnik, pisen=pisen).exists():
            return Response(
                {"pisen": ["Tahle píseň už v tomhle zpěvníku je."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            polozka = PolozkaZpevniku.objects.create(zpevnik=zpevnik, pisen=pisen, kod=kod)
        except IntegrityError:
            # Souběh dvou požadavků mezi kontrolou výš a zápisem — vzácné,
            # ale DB constraint je poslední pojistka, ne jen UI kontrola.
            return Response(
                {"detail": "Kód nebo píseň mezitím obsadil někdo jiný, zkus to znovu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(PisenVZpevnikuSerializer(polozka).data, status=status.HTTP_201_CREATED)


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
                # Kódy přeřazené kvůli kolizi v CÍLOVÉM zpěvníku (bod 4) — UI
                # z toho vypíše "312 → 745: Teenage Dirtbag".
                "prejmenovani_kodu": vysledek["prejmenovani_kodu"],
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
