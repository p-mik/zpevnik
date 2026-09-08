from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import serializers

from .models import Pisen, PolozkaSetlistu, Setlist, Slozka, VerzePisne, Zpevnik
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
