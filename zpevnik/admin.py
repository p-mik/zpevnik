from django.contrib import admin

from .models import (
    Anotace,
    Pisen,
    PolozkaSetlistu,
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
    list_display = ["kod", "nazev", "interpret", "tonina", "tempo"]
    list_filter = ["tonina"]
    search_fields = ["kod", "nazev", "interpret"]
    ordering = ["kod"]
    inlines = [VerzePisneInline]


@admin.register(VerzePisne)
class VerzePisneAdmin(admin.ModelAdmin):
    list_display = ["pisen", "typ_obsahu", "stav", "vlastnik", "upraveno"]
    list_filter = ["typ_obsahu", "stav"]
    search_fields = ["pisen__nazev", "pisen__kod"]


@admin.register(Slozka)
class SlozkaAdmin(admin.ModelAdmin):
    list_display = ["nazev", "rodic"]
    list_filter = ["rodic"]
    search_fields = ["nazev"]


@admin.register(Zpevnik)
class ZpevnikAdmin(admin.ModelAdmin):
    list_display = ["nazev", "slozka", "verejny_token"]
    list_filter = ["slozka"]
    search_fields = ["nazev"]
    filter_horizontal = ["pisne"]


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
