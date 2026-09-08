from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Pisen, PolozkaSetlistu, Setlist, Slozka, VerzePisne, Zpevnik


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class VerzePisneSerializer(serializers.ModelSerializer):
    vlastnik = UserSerializer(read_only=True)

    class Meta:
        model = VerzePisne
        fields = [
            "id",
            "pisen",
            "typ_obsahu",
            "soubor",
            "stav",
            "vlastnik",
            "vytvoreno",
            "upraveno",
        ]
        # soubor: upload je samostatný task, zatím jen read-only průchod pole
        read_only_fields = ["vytvoreno", "upraveno", "soubor"]


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
    class Meta:
        model = VerzePisne
        fields = ["typ_obsahu", "soubor"]


class VerejnaPisenSerializer(serializers.ModelSerializer):
    aktivni_verze = serializers.SerializerMethodField()

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
        ]

    def get_aktivni_verze(self, obj):
        verze = obj.aktivni_verze(user=None)
        if verze is None:
            return None
        return VerejnaVerzeSerializer(verze, context=self.context).data


class VerejnyZpevnikSerializer(serializers.ModelSerializer):
    pisne = VerejnaPisenSerializer(many=True, read_only=True)

    class Meta:
        model = Zpevnik
        fields = ["nazev", "pisne"]
