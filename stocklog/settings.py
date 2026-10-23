import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("STOCKLOG_STATE", BASE_DIR / "var"))
SECRET_KEY = os.environ.get("STOCKLOG_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("Set STOCKLOG_SECRET_KEY in private configuration before starting StockLOG.")
DEBUG = os.environ.get("STOCKLOG_DEBUG") == "1"
ALLOWED_HOSTS = os.environ.get("STOCKLOG_HOSTS", "localhost,127.0.0.1,testserver").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "herd",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "herd.middleware.AccountBoundaryMiddleware",
]
ROOT_URLCONF = "stocklog.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "stocklog.wsgi.application"
AUTH_USER_MODEL = "herd.Account"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("STOCKLOG_DB_NAME", "stocklog"),
        "USER": os.environ.get("STOCKLOG_DB_USER", "stocklog"),
        "PASSWORD": os.environ.get("STOCKLOG_DB_PASSWORD", ""),
        "HOST": os.environ.get("STOCKLOG_DB_HOST", "localhost"),
        "PORT": os.environ.get("STOCKLOG_DB_PORT", ""),
        "OPTIONS": {
            "charset": "utf8mb4",
            "isolation_level": "read committed",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'",
        },
        "CONN_MAX_AGE": 0,
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-au"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = STATE_DIR / "static"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 12 * 3600
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = os.environ.get("STOCKLOG_HTTPS", "1") == "1"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = (
    os.environ.get("STOCKLOG_ORIGINS", "").split(",") if os.environ.get("STOCKLOG_ORIGINS") else []
)
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# Public collected assets must be readable by Caddy without granting it application-secret access.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        "OPTIONS": {"file_permissions_mode": 0o644, "directory_permissions_mode": 0o755},
    },
}
