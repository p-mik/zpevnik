from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import serializers

from .models import (
    Anotace,
    Pisen,
    PolozkaSetlistu,
    Setlist,
    Slozka,
    VerzePisne,
    Zpevnik,
)
from .validatory import bezpecny_puvodni_nazev, zvaliduj_pdf


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class VerzePisneSerializer(serializers.ModelSerializer):
    vlastnik = UserSerializer(read_only=True)
    # Surovou cestu k souboru ven nedáváme — soubor se čte jen přes chráněný
    # endpoint, který kontroluje práva (viz VerzePisneViewSet.soubor).
    soubor = serializers.FileField(write_only=True, required=False, allow_null=True)
    ma_soubor = serializers.SerializerMethodField()

    class Meta:
        model = VerzePisne
        fields = [
            "id",
            "pisen",
            "typ_obsahu",
            "soubor",
            "ma_soubor",
            "puvodni_nazev_souboru",
            "stav",
            "vlastnik",
            "vytvoreno",
            "upraveno",
        ]
        read_only_fields = ["vytvoreno", "upraveno", "puvodni_nazev_souboru"]

    def get_ma_soubor(self, obj):
        return bool(obj.soubor)

    def validate_soubor(self, hodnota):
        if hodnota is None:
            return hodnota
        return zvaliduj_pdf(hodnota)

    def _uloz_puvodni_nazev(self, validated_data):
        """Jméno od klienta si schovej jen jako popisek, očištěné."""
        soubor = validated_data.get("soubor")
        if soubor is not None:
            validated_data["puvodni_nazev_souboru"] = bezpecny_puvodni_nazev(
                getattr(soubor, "name", "")
            )
        return validated_data

    def create(self, validated_data):
        return super().create(self._uloz_puvodni_nazev(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._uloz_puvodni_nazev(validated_data))


# --- Anotace (fáze 2a) ---
# Souřadnice jsou zlomky rozměru stránky (0–1), NE pixely: tytéž poznámky se
# čtou na PC i na tabletu, při zoomu a po otočení displeje. Pixely by platily
# jen pro to jedno okno, ve kterém vznikly.

STYLY_ANOTACI = ["normal", "mono", "akord", "znacka"]
VELIKOSTI_ANOTACI = ["mala", "normalni", "velka"]
MAX_ANOTACI = 200
MAX_DELKA_TEXTU = 2000


class AnotaceObjektSerializer(serializers.Serializer):
    """Jeden objekt v anotační vrstvě. Ve v1 jen textové pole ve čtyřech stylech."""

    id = serializers.CharField(max_length=64)
    strana = serializers.IntegerField(min_value=1)
    x = serializers.FloatField(min_value=0, max_value=1)
    y = serializers.FloatField(min_value=0, max_value=1)
    sirka = serializers.FloatField(min_value=0.02, max_value=1)
    text = serializers.CharField(
        max_length=MAX_DELKA_TEXTU, allow_blank=True, trim_whitespace=False
    )
    styl = serializers.ChoiceField(choices=STYLY_ANOTACI, default="normal")
    # `default` platí i při čtení: poznámky uložené před zavedením velikosti
    # nemají klíč vůbec a vyjdou jako "normalni", místo aby serializaci shodily.
    velikost = serializers.ChoiceField(choices=VELIKOSTI_ANOTACI, default="normalni")

    def validate(self, attrs):
        # Pole nesmí přetéct přes pravý okraj stránky — jinak by se na užším
        # displeji ořízlo a text by zmizel. Drobná tolerance kvůli tomu, že
        # klient počítá v pixelech a dělí je šířkou stránky.
        if attrs["x"] + attrs["sirka"] > 1.0001:
            raise serializers.ValidationError(
                "Pole přesahuje pravý okraj stránky (x + sirka musí být nejvýš 1)."
            )
        return attrs


class AnotaceSerializer(serializers.ModelSerializer):
    data = AnotaceObjektSerializer(many=True)

    class Meta:
        model = Anotace
        fields = ["data", "upraveno"]
        read_only_fields = ["upraveno"]

    def validate_data(self, value):
        if len(value) > MAX_ANOTACI:
            raise serializers.ValidationError(
                f"Na jednu verzi jde uložit nejvýš {MAX_ANOTACI} poznámek."
            )
        identifikatory = [objekt["id"] for objekt in value]
        if len(set(identifikatory)) != len(identifikatory):
            raise serializers.ValidationError("Poznámky mají duplicitní id.")
        return value


class PisenListSerializer(serializers.ModelSerializer):
    """Lehký seznam pro rychlý scroll — bez vnořených verzí."""

    class Meta:
        model = Pisen
        fields = ["id", "kod", "nazev", "interpret"]


class PisenDetailSerializer(serializers.ModelSerializer):
    verze = VerzePisneSerializer(many=True, read_only=True)
    aktivni_verze = serializers.SerializerMethodField()

    class Meta:
        model = Pisen
        fields = [
            "id",
            "kod",
            "nazev",
            "interpret",
            "tonina",
            "capo",
            "tempo",
            "odkaz_nahravka",
            "verze",
            "aktivni_verze",
        ]

    def get_aktivni_verze(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        verze = obj.aktivni_verze(user=user)
        if verze is None:
            return None
        return VerzePisneSerializer(verze, context=self.context).data


class SlozkaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slozka
        fields = ["id", "nazev", "rodic"]


class ZpevnikSerializer(serializers.ModelSerializer):
    pisne = PisenListSerializer(many=True, read_only=True)
    pisne_ids = serializers.PrimaryKeyRelatedField(
        source="pisne",
        queryset=Pisen.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )
    verejny_token = serializers.SerializerMethodField()

    class Meta:
        model = Zpevnik
        fields = ["id", "nazev", "slozka", "pisne", "pisne_ids", "verejny_token"]

    def get_verejny_token(self, obj):
        """Token je sdílitelný odkaz — viditelný jen adminovi, ne každému členovi."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_staff:
            return obj.verejny_token
        return None


class PolozkaSetlistuSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolozkaSetlistu
        fields = ["id", "pisen", "poradi"]


class SetlistSerializer(serializers.ModelSerializer):
    polozky = PolozkaSetlistuSerializer(many=True)

    class Meta:
        model = Setlist
        fields = ["id", "nazev", "vytvoreno", "polozky"]
        read_only_fields = ["vytvoreno"]

    def create(self, validated_data):
        polozky_data = validated_data.pop("polozky", [])
        setlist = Setlist.objects.create(**validated_data)
        self._sync_polozky(setlist, polozky_data)
        return setlist

    def update(self, instance, validated_data):
        polozky_data = validated_data.pop("polozky", None)
        instance.nazev = validated_data.get("nazev", instance.nazev)
        instance.save()
        if polozky_data is not None:
            instance.polozky.all().delete()
            self._sync_polozky(instance, polozky_data)
        return instance

    def _sync_polozky(self, setlist, polozky_data):
        PolozkaSetlistu.objects.bulk_create(
            [PolozkaSetlistu(setlist=setlist, **polozka) for polozka in polozky_data]
        )


# --- Veřejný (neautentizovaný) zpěvník — minimální průchod dat ---


class VerejnaVerzeSerializer(serializers.ModelSerializer):
    """Jen typ obsahu — cesta k souboru na disku ven nepatří ani tady.

    Soubor se čte přes /api/verejny/<token>/pisen/<kod>/soubor/, což znovu
    ověří, že píseň v tom zpěvníku opravdu je.
    """

    class Meta:
        model = VerzePisne
        fields = ["typ_obsahu"]


class VerejnaPisenSerializer(serializers.ModelSerializer):
    aktivni_verze = serializers.SerializerMethodField()
    soubor_url = serializers.SerializerMethodField()

    class Meta:
        model = Pisen
        fields = [
            "kod",
            "nazev",
            "interpret",
            "tonina",
            "capo",
            "tempo",
            "odkaz_nahravka",
            "aktivni_verze",
            "soubor_url",
        ]

    def get_aktivni_verze(self, obj):
        verze = obj.aktivni_verze(user=None)
        if verze is None:
            return None
        return VerejnaVerzeSerializer(verze, context=self.context).data

    def get_soubor_url(self, obj):
        verze = obj.aktivni_verze(user=None)
        token = self.context.get("verejny_token")
        if verze is None or not verze.soubor or not token:
            return None
        return reverse(
            "verejny-soubor", kwargs={"token": token, "kod": obj.kod}
        )


class VerejnyZpevnikSerializer(serializers.ModelSerializer):
    pisne = VerejnaPisenSerializer(many=True, read_only=True)

    class Meta:
        model = Zpevnik
        fields = ["nazev", "pisne"]


# --- Hromadný import (fáze 1e) — validace POTVRZENÉHO plánu, ne parsování ---
# Parsování PDF proběhlo na klientovi; tady se jen ověřuje TVAR plánu, který
# poslal. Obsahová validace (kódy, rozsahy stránek) je v zpevnik/import_pisni.py,
# protože potřebuje znát skutečný počet stran nahraného PDF.


class ImportPisenPlanSerializer(serializers.Serializer):
    kod = serializers.IntegerField(min_value=1)
    nazev = serializers.CharField(max_length=255)
    interpret = serializers.CharField(
        max_length=255, allow_blank=True, required=False, default=""
    )
    stranky = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False
    )


class ImportKategoriePlanSerializer(serializers.Serializer):
    digit = serializers.CharField(max_length=1, min_length=1)
    nazev = serializers.CharField(max_length=255)
    vytvorit = serializers.BooleanField(default=True)


class ImportCelyZpevnikPlanSerializer(serializers.Serializer):
    """Jeden Zpevnik se všemi importovanými písněmi — "ta kniha jako celek",
    nezávisle na Slozka/Zpevnik rozpadu po kategoriích (viz import_pisni.py).
    """

    nazev = serializers.CharField(max_length=255)
    vytvorit = serializers.BooleanField(default=True)


class ImportPlanSerializer(serializers.Serializer):
    pisne = ImportPisenPlanSerializer(many=True)
    kategorie = ImportKategoriePlanSerializer(many=True, required=False, default=list)
    cely_zpevnik = ImportCelyZpevnikPlanSerializer(required=False, allow_null=True, default=None)

    def validate_pisne(self, value):
        if not value:
            raise serializers.ValidationError("Plán neobsahuje žádnou píseň.")
        return value
