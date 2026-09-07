from django.conf import settings
from django.db import models


class Pisen(models.Model):
    """Kmenová píseň — nese jen metadata, obsah nesou verze."""

    kod = models.PositiveIntegerField(unique=True, verbose_name="Kód")
    nazev = models.CharField(max_length=255)
    interpret = models.CharField(max_length=255, blank=True)
    tonina = models.CharField(max_length=20, blank=True, verbose_name="Tónina")
    capo = models.PositiveSmallIntegerField(null=True, blank=True)
    tempo = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="BPM, pro vizuální metronom"
    )
    odkaz_nahravka = models.URLField(blank=True, verbose_name="Odkaz na nahrávku")

    class Meta:
        verbose_name = "Píseň"
        verbose_name_plural = "Písně"
        ordering = ["kod"]

    def __str__(self):
        return f"{self.kod} — {self.nazev}"


class VerzePisne(models.Model):
    """Konkrétní obsahová verze písně (PDF, později text/ChordPro)."""

    TYP_PDF = "pdf"
    TYP_TEXT = "text"
    TYP_OBSAHU_CHOICES = [
        (TYP_PDF, "PDF"),
        (TYP_TEXT, "Text"),
    ]

    STAV_DRAFT = "draft"
    STAV_DOWNLOAD = "download"
    STAV_CONFIRMED = "confirmed"
    STAV_HANDMADE = "handmade"
    STAV_PERSONAL = "personal"
    STAV_CHOICES = [
        (STAV_DRAFT, "Koncept"),
        (STAV_DOWNLOAD, "Stažené"),
        (STAV_CONFIRMED, "Potvrzené"),
        (STAV_HANDMADE, "Ručně vyrobené"),
        (STAV_PERSONAL, "Osobní"),
    ]

    pisen = models.ForeignKey(Pisen, on_delete=models.CASCADE, related_name="verze")
    typ_obsahu = models.CharField(
        max_length=10, choices=TYP_OBSAHU_CHOICES, default=TYP_PDF
    )
    soubor = models.FileField(upload_to="verze_pisni/", blank=True, null=True)
    stav = models.CharField(max_length=20, choices=STAV_CHOICES, default=STAV_DRAFT)
    vlastnik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verze_pisni",
        null=True,
        blank=True,
        help_text="Povinné jen u stavu 'personal'",
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Verze písně"
        verbose_name_plural = "Verze písní"
        ordering = ["-upraveno"]

    def __str__(self):
        return f"{self.pisen} ({self.get_stav_display()})"


class Slozka(models.Model):
    """Stromová struktura pro organizaci zpěvníků."""

    nazev = models.CharField(max_length=255)
    rodic = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="podslozky",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Složka"
        verbose_name_plural = "Složky"
        ordering = ["nazev"]

    def __str__(self):
        return self.nazev


class Zpevnik(models.Model):
    nazev = models.CharField(max_length=255)
    slozka = models.ForeignKey(
        Slozka,
        on_delete=models.SET_NULL,
        related_name="zpevniky",
        null=True,
        blank=True,
    )
    verejny_token = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        help_text="Neuhodnutelný token pro veřejný (read-only) odkaz",
    )
    pisne = models.ManyToManyField(Pisen, related_name="zpevniky", blank=True)

    class Meta:
        verbose_name = "Zpěvník"
        verbose_name_plural = "Zpěvníky"
        ordering = ["nazev"]

    def __str__(self):
        return self.nazev


class Setlist(models.Model):
    """Trvalé pojmenované pořadí písní, nezávislé na session."""

    nazev = models.CharField(max_length=255)
    pisne = models.ManyToManyField(
        Pisen, through="PolozkaSetlistu", related_name="setlisty"
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Setlist"
        verbose_name_plural = "Setlisty"
        ordering = ["-vytvoreno"]

    def __str__(self):
        return self.nazev


class PolozkaSetlistu(models.Model):
    setlist = models.ForeignKey(
        Setlist, on_delete=models.CASCADE, related_name="polozky"
    )
    pisen = models.ForeignKey(Pisen, on_delete=models.CASCADE)
    poradi = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Položka setlistu"
        verbose_name_plural = "Položky setlistu"
        ordering = ["poradi"]

    def __str__(self):
        return f"{self.setlist} #{self.poradi}: {self.pisen}"


class Session(models.Model):
    """Živý kanál kapelník + členové, řízený pollingem na frontendu."""

    kapelnik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions_jako_kapelnik",
    )
    setlist = models.ForeignKey(
        Setlist,
        on_delete=models.SET_NULL,
        related_name="sessions",
        null=True,
        blank=True,
    )
    aktualni_pozice = models.PositiveIntegerField(default=0)
    aktivni = models.BooleanField(default=True)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Session"
        verbose_name_plural = "Session"
        ordering = ["-vytvoreno"]

    def __str__(self):
        return f"Session {self.pk} ({self.kapelnik})"


class Anotace(models.Model):
    """Poznámková overlay vrstva nad PDF (nebo nad kmenovou písní)."""

    verze_pisne = models.ForeignKey(
        VerzePisne,
        on_delete=models.CASCADE,
        related_name="anotace",
        null=True,
        blank=True,
    )
    pisen = models.ForeignKey(
        Pisen,
        on_delete=models.CASCADE,
        related_name="anotace",
        null=True,
        blank=True,
    )
    vlastnik = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="anotace"
    )
    data = models.JSONField(
        default=list,
        help_text="Seznam objektů: textbox, akord, tab_grid, znacka — s pozicí (x, y, strana)",
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Anotace"
        verbose_name_plural = "Anotace"
        ordering = ["-upraveno"]

    def __str__(self):
        cil = self.verze_pisne or self.pisen
        return f"Anotace {self.vlastnik} — {cil}"
