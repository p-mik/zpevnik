from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-change-in-production")

DEBUG = os.environ.get("DEBUG", "False") == "True"

# Nezávislé na DEBUGu schválně — Django test runner DEBUG vždy vynutí na
# False (viz django.test.utils.setup_test_environment), takže by kontroly
# vázané na "not DEBUG" vyskakovaly i při běžném `manage.py test` v lokálním
# vývoji. Výchozí hodnota je "production" (bezpečné selhání zavřeně — kdyby
# se proměnná v produkci zapomněla nastavit, kontroly dál platí); lokální
# `.env` ji přepíná na "development".
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS", "zpevnik.upupaepops.cz,localhost,127.0.0.1"
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "zpevnik",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "zpevnik"),
        "USER": os.environ.get("DB_USER", "zpevnik"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "cs"
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media"))

# Vlastní limit pro upload. Nginx má svůj (client_max_body_size 200m), ale na ten
# se nespoléháme — Django musí odmítnout velký soubor samo, i kdyby šel request
# mimo nginx. Kontroluje se v zpevnik/validatory.py, ne přes FILE_UPLOAD_*
# (ty řeší jen buffer v paměti vs. temp soubor, ne maximální velikost).
MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "25")) * 1024 * 1024

# Chráněné soubory posílá nginx přes X-Accel-Redirect (viz zpevnik/soubory.py).
# V PRODUKCI MUSÍ ZŮSTAT True — Django nesmí streamovat soubory samo.
# False je jen pro lokální vývoj bez nginx; hlídá to system check zpevnik.E001.
X_ACCEL_REDIRECT = os.environ.get("X_ACCEL_REDIRECT", "True") == "True"
X_ACCEL_PREFIX = "/protected/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Za nginx reverse proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Důvěryhodné origins pro CSRF (nutné pro HTTPS za reverse proxy)
_csrf_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "https://zpevnik.upupaepops.cz")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]
