from rest_framework import permissions

from .models import VerzePisne


class IsStaffOrReadOnly(permissions.BasePermission):
    """Čtení pro každého přihlášeného, zápis jen pro adminy (is_staff)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff


class VerzePisnePermission(permissions.BasePermission):
    """Čtení pro každého přihlášeného. Zápis: admin cokoliv, člen jen vlastní personal verzi."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.stav == VerzePisne.STAV_PERSONAL and obj.vlastnik_id == request.user.id
