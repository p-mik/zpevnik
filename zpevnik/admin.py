from django.contrib import admin

from .models import (
    Anotace,
    Pisen,
    PolozkaSetlistu,
    PolozkaZpevniku,
    Session,
    Setlist,
    Slozka,
    VerzePisne,
    Zpevnik,
)


class VerzePisneInline(admin.TabularInline):
    model = VerzePisne
    extra = 0
    fields = ["typ_obsahu", "soubor", "stav", "vlastnik", "upraveno"]
    readonly_fields = ["upraveno"]


@admin.register(Pisen)
class PisenAdmin(admin.ModelAdmin):
    list_display = ["nazev", "interpret", "tonina", "tempo"]
    list_filter = ["tonina"]
    search_fields = ["nazev", "interpret"]
    ordering = ["nazev"]
    inlines = [VerzePisneInline]


@admin.register(VerzePisne)
class VerzePisneAdmin(admin.ModelAdmin):
    list_display = ["pisen", "typ_obsahu", "stav", "vlastnik", "puvodni_nazev_souboru", "upraveno"]
    list_filter = ["typ_obsahu", "stav"]
    search_fields = ["pisen__nazev", "puvodni_nazev_souboru"]
    readonly_fields = ["puvodni_nazev_souboru"]


@admin.register(Slozka)
class SlozkaAdmin(admin.ModelAdmin):
    list_display = ["nazev", "rodic"]
    list_filter = ["rodic"]
    search_fields = ["nazev"]


@admin.action(description="Vygenerovat veřejný odkaz (token)")
def vygenerovat_verejny_token(modeladmin, request, queryset):
    for zpevnik in queryset:
        zpevnik.vygeneruj_verejny_token()


class PolozkaZpevnikuInline(admin.TabularInline):
    model = PolozkaZpevniku
    extra = 1
    fields = ["kod", "pisen"]
    ordering = ["kod"]


@admin.register(Zpevnik)
class ZpevnikAdmin(admin.ModelAdmin):
    list_display = ["nazev", "slozka", "verejny_token"]
    list_filter = ["slozka"]
    search_fields = ["nazev"]
    # `filter_horizontal` na `pisne` nejde — M2M s explicitním `through`
    # (kód je vlastnost zařazení, ne písně, viz models.py) potřebuje inline
    # na sám through model, ne widget na holou M2M.
    inlines = [PolozkaZpevnikuInline]
    actions = [vygenerovat_verejny_token]


class PolozkaSetlistuInline(admin.TabularInline):
    model = PolozkaSetlistu
    extra = 1
    fields = ["poradi", "pisen"]
    ordering = ["poradi"]


@admin.register(Setlist)
class SetlistAdmin(admin.ModelAdmin):
    list_display = ["nazev", "vytvoreno"]
    search_fields = ["nazev"]
    inlines = [PolozkaSetlistuInline]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["id", "kapelnik", "setlist", "aktualni_pozice", "aktivni", "vytvoreno"]
    list_filter = ["aktivni"]
    search_fields = ["kapelnik__username"]


@admin.register(Anotace)
class AnotaceAdmin(admin.ModelAdmin):
    list_display = ["vlastnik", "pisen", "verze_pisne", "upraveno"]
    list_filter = ["vlastnik"]
    search_fields = ["pisen__nazev"]
