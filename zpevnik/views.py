from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def index(request):
    """Servíruje zbuildovanou React SPA."""
    html = settings.BASE_DIR / "static" / "frontend" / "index.html"
    return HttpResponse(html.read_text(encoding="utf-8"), content_type="text/html")
