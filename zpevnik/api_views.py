from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pisen, PolozkaSetlistu, Setlist, Slozka, VerzePisne, Zpevnik
from .permissions import IsStaffOrReadOnly, VerzePisnePermission
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
        serializer = VerejnyZpevnikSerializer(zpevnik, context={"request": request})
        return Response(serializer.data)


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
