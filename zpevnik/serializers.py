from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import serializers

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
            "cislo",
            "pisen",
            "typ_obsahu",
            "soubor",
            "ma_soubor",
            "puvodni_nazev_souboru",
            "stav",
            "zdroj",
            "vlastnik",
            "vytvoreno",
            "upraveno",
        ]
        # `zdroj` je čtenářské i tady: nastavuje ho jen server (viz
        # PisenViewSet.verze_akordy / VerzePisneViewSet.akordy), nikdy přímo
        # klient přes obecný create/update — jinak by šlo založit zdroj=akordy
        # bez akordového zápisu a bez vygenerovaného PDF, což by porušilo
        # invariant "soubor u akordů je vždycky vygenerovaný, nikdy nahraný".
        # `cislo` ze stejného důvodu čtenářské — přiděluje ho výhradně server
        # (Pisen.dalsi_cislo_verze), viz perform_create níž.
        read_only_fields = [
            "vytvoreno",
            "upraveno",
            "puvodni_nazev_souboru",
            "zdroj",
            "cislo",
        ]

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


# --- Akordový zápis, schéma 2 (PC_zpevnik_akordovy_zapis_upravy.md) ---
# Zdrojová data pro generovaný PDF (viz akordy_pdf.py) — VerzePisne se
# `zdroj='akordy'` nese tenhle JSON MÍSTO nahraného souboru; `soubor` je z
# něj vygenerovaný artefakt (viz VerzePisneViewSet.akordy).
#
# Schéma 1 (fáze 1–2) se NEPODPORUJE ani nepřevádí — v produkci nikdy nic
# nebylo pushnuto, takže není co migrovat (viz zadání úprav). `schema` je
# napevno 2; jakýkoliv jiný zápis serializer rovnou odmítne.
#
# Sekce je teď blok, ne popisek řádku: `sekce[]` → `radky[]` → `takty[]` →
# `bunky[]`. `takty[].takt` je VOLITELNÝ přepis výchozího taktu (viz
# PC_zpevnik_akordovy_zapis_upravy.md bod 2) — když chybí, platí dokumentu
# vlastní `takt`. `repetice` žije na SEKCI, ne na řádku: indexuje takty
# napříč VŠEMI řádky té sekce (0-based, `do_taktu` včetně) — umožňuje
# repetici přes víc řádků v rámci jedné sekce, ne přes sekce.

MAX_RADKU_AKORDY = 200
MAX_ZNAKU_BUNKA = 16
MAX_TAKTU_NA_RADEK = 64
MAX_DELKA_SEKCE = 30
MAX_SEKCI = 50


class TaktSerializer(serializers.Serializer):
    """Tvar {dob, hodnota} — použitý jak pro výchozí takt dokumentu, tak
    pro přepis jednotlivého taktu v řádku (stejná struktura, jiný kontext)."""

    dob = serializers.IntegerField(min_value=1, max_value=32)
    hodnota = serializers.IntegerField(min_value=1, max_value=32)


class RepeticeSerializer(serializers.Serializer):
    # Indexy taktů NAPŘÍČ VŠEMI ŘÁDKY SEKCE, 0-based, `do_taktu` včetně —
    # validace proti skutečnému počtu taktů sekce (a proti překryvu) je až
    # na AkordovyZapisSerializer.validate, kde je zná oboje najednou.
    od_taktu = serializers.IntegerField(min_value=0)
    do_taktu = serializers.IntegerField(min_value=0)
    krat = serializers.IntegerField(min_value=2, max_value=16)

    def validate(self, attrs):
        if attrs["do_taktu"] < attrs["od_taktu"]:
            raise serializers.ValidationError("`do_taktu` nesmí být před `od_taktu`.")
        return attrs


class TaktVRadkuSerializer(serializers.Serializer):
    """Jeden takt (bar) uvnitř řádku. `bunky` — prázdná buňka = drží se
    předchozí akord (validní hodnota, ne chyba). `takt` chybí = platí
    výchozí takt dokumentu; jeho délka musí sedět s `len(bunky)` — to se
    ověřuje až na AkordovyZapisSerializer.validate, kde je výchozí takt
    po ruce."""

    bunky = serializers.ListField(
        child=serializers.CharField(max_length=MAX_ZNAKU_BUNKA, allow_blank=True),
        allow_empty=False,
    )
    takt = TaktSerializer(required=False)


class RadekZapisuSerializer(serializers.Serializer):
    takty = TaktVRadkuSerializer(many=True, allow_empty=False)

    def validate_takty(self, value):
        if len(value) > MAX_TAKTU_NA_RADEK:
            raise serializers.ValidationError(f"Nejvýš {MAX_TAKTU_NA_RADEK} taktů na řádek.")
        return value


class SekceSerializer(serializers.Serializer):
    nazev = serializers.CharField(max_length=MAX_DELKA_SEKCE, allow_blank=True, default="")
    radky = RadekZapisuSerializer(many=True, allow_empty=True)
    repetice = RepeticeSerializer(many=True, required=False, default=list)


class AkordovyZapisSerializer(serializers.Serializer):
    schema = serializers.IntegerField(min_value=2, max_value=2)
    takt = TaktSerializer()
    tempo = serializers.IntegerField(min_value=20, max_value=400, required=False, allow_null=True)
    sekce = SekceSerializer(many=True, allow_empty=True)

    def validate_sekce(self, value):
        if len(value) > MAX_SEKCI:
            raise serializers.ValidationError(f"Nejvýš {MAX_SEKCI} sekcí.")
        celkem_radku = sum(len(s["radky"]) for s in value)
        if celkem_radku > MAX_RADKU_AKORDY:
            raise serializers.ValidationError(f"Nejvýš {MAX_RADKU_AKORDY} řádků celkem.")
        return value

    def validate(self, attrs):
        dob_vychozi = attrs["takt"]["dob"]
        for i_sekce, sekce in enumerate(attrs["sekce"]):
            pocet_taktu_v_sekci = 0
            for i_radek, radek in enumerate(sekce["radky"]):
                for i_takt, takt_v_radku in enumerate(radek["takty"]):
                    efektivni_dob = takt_v_radku.get("takt", {}).get("dob", dob_vychozi)
                    pocet_bunek = len(takt_v_radku["bunky"])
                    if pocet_bunek != efektivni_dob:
                        raise serializers.ValidationError(
                            f"Sekce {i_sekce + 1}, řádek {i_radek + 1}, takt {i_takt + 1}: "
                            f"počet buněk ({pocet_bunek}) musí sedět s taktem ({efektivni_dob})."
                        )
                    pocet_taktu_v_sekci += 1

            obsazene = set()
            for rep in sekce["repetice"]:
                if rep["do_taktu"] >= pocet_taktu_v_sekci:
                    raise serializers.ValidationError(
                        f"Sekce {i_sekce + 1}: repetice odkazuje na takt mimo sekci."
                    )
                rozsah = set(range(rep["od_taktu"], rep["do_taktu"] + 1))
                if obsazene & rozsah:
                    raise serializers.ValidationError(
                        f"Sekce {i_sekce + 1}: repetice se v rámci sekce překrývají."
                    )
                obsazene |= rozsah
        return attrs


class PisenListSerializer(serializers.ModelSerializer):
    """Lehký seznam pro rychlý scroll — bez vnořených verzí.

    Bez `kod` schválně: kód je vlastnost zařazení do KONKRÉTNÍHO zpěvníku
    (viz PolozkaZpevniku), ne písně samotné — stejná píseň může mít v
    různých zpěvnících různá čísla. V plochém seznamu napříč vším žádné
    jednoznačné číslo neexistuje; kód se ukazuje jen tam, kde je jasné, o
    kterém zpěvníku je řeč (viz PisenVZpevnikuSerializer)."""

    class Meta:
        model = Pisen
        fields = ["id", "nazev", "interpret"]


class ZarazeniZpevnikuSerializer(serializers.ModelSerializer):
    """Jedno zařazení písně do zpěvníku — s jeho vlastním kódem. Píseň jich
    může mít víc (různé zpěvníky, různá čísla), proto je to seznam na
    PisenDetailSerializer, ne jedno pole."""

    zpevnik_nazev = serializers.CharField(source="zpevnik.nazev", read_only=True)

    class Meta:
        model = PolozkaZpevniku
        fields = ["id", "zpevnik", "zpevnik_nazev", "kod"]


class PisenDetailSerializer(serializers.ModelSerializer):
    verze = VerzePisneSerializer(many=True, read_only=True)
    aktivni_verze = serializers.SerializerMethodField()
    zarazeni = ZarazeniZpevnikuSerializer(source="polozky_zpevniku", many=True, read_only=True)

    class Meta:
        model = Pisen
        fields = [
            "id",
            "nazev",
            "interpret",
            "tonina",
            "capo",
            "tempo",
            "odkaz_nahravka",
            "verze",
            "aktivni_verze",
            "zarazeni",
        ]

    def get_aktivni_verze(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        verze = obj.aktivni_verze(user=user)
        if verze is None:
            return None
        return VerzePisneSerializer(verze, context=self.context).data


class PisenVZpevnikuSerializer(serializers.ModelSerializer):
    """Píseň tak, jak se objevuje v KONKRÉTNÍM zpěvníku — s jeho vlastním
    kódem. `id` je PK písně (pro odkazy na /pisne/<id>/…), `polozka_id` je PK
    tohohle konkrétního zařazení (pro budoucí editaci/přesun mezi zpěvníky)."""

    id = serializers.IntegerField(source="pisen_id", read_only=True)
    polozka_id = serializers.IntegerField(source="id", read_only=True)
    nazev = serializers.CharField(source="pisen.nazev", read_only=True)
    interpret = serializers.CharField(source="pisen.interpret", read_only=True)

    class Meta:
        model = PolozkaZpevniku
        fields = ["id", "polozka_id", "kod", "nazev", "interpret"]


class PridatPisenSerializer(serializers.Serializer):
    """Vstup pro ZpevnikViewSet.pridat_pisen — zařazení existující písně do
    zpěvníku pod daným kódem. Kolize (kód i píseň) se ověřují až ve view,
    kde je zpěvník už po ruce (viz PolozkaZpevniku constraints)."""

    pisen = serializers.PrimaryKeyRelatedField(queryset=Pisen.objects.all())
    kod = serializers.IntegerField(min_value=1)


class SlozkaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slozka
        fields = ["id", "nazev", "rodic"]


class ZpevnikSerializer(serializers.ModelSerializer):
    # Přes `polozky` (PolozkaZpevniku), ne přímo `pisne` — potřebujeme kód
    # PLATNÝ V TOMHLE zpěvníku, ne píseň samotnou. Řazení podle kódu jde
    # zadarmo z PolozkaZpevniku.Meta.ordering.
    pisne = PisenVZpevnikuSerializer(source="polozky", many=True, read_only=True)
    # Zápisové přidávání/přesun písní (s řešením kolizí kódů) je zatím jen
    # přes admin/import — `pisne_ids` je pryč, protože M2M s `through`
    # vyžadujícím extra pole (kód) neumí Django `.set()` jednou hodnotou pro
    # všechny najednou. Vrátí se, až bude editace/přesun mezi zpěvníky
    # hotová pořádně (viz zadání „později").
    verejny_token = serializers.SerializerMethodField()

    class Meta:
        model = Zpevnik
        fields = ["id", "nazev", "slozka", "pisne", "verejny_token"]

    def validate_nazev(self, hodnota):
        # Model nemá DB-level unique=True (produkce už dřív vznikla přes
        # import, kde se stejnojmenné zpěvníky slučují schválně přes
        # get_or_create — viz import_pisni.py) — unikátnost pro nově
        # ZAKLÁDANÉ zpěvníky (viz PC_zpevnik_sprava.md bod 2) se proto hlídá
        # tady, ne migrací s DB constraintem.
        dotaz = Zpevnik.objects.filter(nazev=hodnota)
        if self.instance is not None:
            dotaz = dotaz.exclude(pk=self.instance.pk)
        if dotaz.exists():
            raise serializers.ValidationError("Zpěvník s tímhle názvem už existuje.")
        return hodnota

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
    """Píseň ve VEŘEJNÉM zpěvníku — `obj` je PolozkaZpevniku (ne Pisen), kód
    je platný jen v rámci TOHOTO zpěvníku (viz PisenVZpevnikuSerializer,
    stejný princip)."""

    kod = serializers.IntegerField(read_only=True)
    nazev = serializers.CharField(source="pisen.nazev", read_only=True)
    interpret = serializers.CharField(source="pisen.interpret", read_only=True)
    tonina = serializers.CharField(source="pisen.tonina", read_only=True)
    capo = serializers.IntegerField(source="pisen.capo", read_only=True)
    tempo = serializers.IntegerField(source="pisen.tempo", read_only=True)
    odkaz_nahravka = serializers.URLField(source="pisen.odkaz_nahravka", read_only=True)
    aktivni_verze = serializers.SerializerMethodField()
    soubor_url = serializers.SerializerMethodField()

    class Meta:
        model = PolozkaZpevniku
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
        verze = obj.pisen.aktivni_verze(user=None)
        if verze is None:
            return None
        return VerejnaVerzeSerializer(verze, context=self.context).data

    def get_soubor_url(self, obj):
        verze = obj.pisen.aktivni_verze(user=None)
        token = self.context.get("verejny_token")
        if verze is None or not verze.soubor or not token:
            return None
        return reverse(
            "verejny-soubor", kwargs={"token": token, "kod": obj.kod}
        )


class VerejnyZpevnikSerializer(serializers.ModelSerializer):
    # Přes `polozky`, ne `pisne` přímo — stejný důvod jako u ZpevnikSerializer.
    pisne = VerejnaPisenSerializer(source="polozky", many=True, read_only=True)

    class Meta:
        model = Zpevnik
        fields = ["nazev", "pisne"]


# --- Hromadný import (fáze 1e/2b) — validace POTVRZENÉHO plánu, ne parsování ---
# Parsování PDF proběhlo na klientovi; tady se jen ověřuje TVAR plánu, který
# poslal. Obsahová validace (kódy, rozsahy stránek) je v zpevnik/import_pisni.py,
# protože potřebuje znát skutečný počet stran nahraného PDF.
#
# `kod` je od fáze 2b vlastnost zařazení do zpěvníku (viz PolozkaZpevniku),
# ne písně — pořád ho ale posílá JEDEN plán jako "číslo, pod kterým tahle
# píseň bude ve VŠECH zpěvnících, co se tímhle importem zakládají" (kategorie
# i celý zpěvník dohromady tvoří jednu knihu, číslování je jedno pro obojí).


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
    """Cíl importu (PC_zpevnik_sprava.md bod 4) — JEDEN Zpevnik, do kterého
    se zařadí VŠECHNY importované písně, nezávisle na Slozka/Zpevnik
    rozpadu po kategoriích níž (viz import_pisni.py). Buď existující
    (`existujici_id`), nebo nový (`nazev`) — právě jedno z obojího."""

    existujici_id = serializers.PrimaryKeyRelatedField(
        queryset=Zpevnik.objects.all(), required=False, allow_null=True, default=None
    )
    nazev = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("existujici_id") and attrs.get("nazev"):
            raise serializers.ValidationError(
                "Zadej buď existující zpěvník, nebo název nového — ne obojí."
            )
        if not attrs.get("existujici_id") and not attrs.get("nazev"):
            raise serializers.ValidationError("Vyber cílový zpěvník, nebo zadej název nového.")
        return attrs


class ImportPlanSerializer(serializers.Serializer):
    pisne = ImportPisenPlanSerializer(many=True)
    kategorie = ImportKategoriePlanSerializer(many=True, required=False, default=list)
    # Povinné — import je vždycky DO KONKRÉTNÍHO zpěvníku (viz
    # PC_zpevnik_sprava.md bod 4), `kategorie` je jen volitelné rozdělení
    # navíc pro procházení podle první číslice kódu.
    cely_zpevnik = ImportCelyZpevnikPlanSerializer()

    def validate_pisne(self, value):
        if not value:
            raise serializers.ValidationError("Plán neobsahuje žádnou píseň.")
        return value
