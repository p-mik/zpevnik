from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def index(request):
    """Servíruje zbuildovanou React SPA.

    `no-cache` schválně: index.html je jediná NEhashovaná část frontendu a
    ukazuje na hashované bundly. Bez téhle hlavičky si ho prohlížeč
    heuristicky zapamatuje a po každém nasazení drží starou appku, dokud
    uživatel neudělá tvrdý refresh — samotné bundly (WhiteNoise, dlouhá
    cache) jsou v pořádku, právě proto že mají v názvu hash obsahu.
    """
    html = settings.BASE_DIR / "static" / "frontend" / "index.html"
    response = HttpResponse(html.read_text(encoding="utf-8"), content_type="text/html")
    response["Cache-Control"] = "no-cache"
    return response
