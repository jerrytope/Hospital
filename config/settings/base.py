"""Base settings shared by every environment."""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")

INSTALLED_APPS = [
    # Project apps
    "apps.core",
    "apps.accounts",
    "apps.taxonomy",
    "apps.pages",
    "apps.about",
    "apps.programs",
    "apps.emergencies",
    "apps.countries",
    "apps.stories",
    "apps.resources",
    "apps.newsletter",
    "apps.giving",
    "apps.payments",
    "apps.fundraising",
    "apps.involvement",
    "apps.dashboard",
    # Wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.contrib.routable_page",
    "wagtail.contrib.search_promotions",
    "wagtail.contrib.sitemaps",
    "wagtail.contrib.table_block",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    # Third party
    "django_filters",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "allauth",
    "allauth.account",
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.accounts.middleware.AdminTwoFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
                "apps.core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600
    )
}
# Wagtail's search index uses PostgreSQL full-text fields, which need this app on PostgreSQL.
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    INSTALLED_APPS.append("django.contrib.postgres")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = os.environ.get("TIME_ZONE", "Africa/Lagos")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10_000

# --- Wagtail ---------------------------------------------------------------
WAGTAIL_SITE_NAME = os.environ.get("WAGTAIL_SITE_NAME", "Haven Medical Relief")
WAGTAILADMIN_BASE_URL = SITE_URL
WAGTAILIMAGES_IMAGE_MODEL = "core.CustomImage"
WAGTAILIMAGES_EXTENSIONS = ["gif", "jpg", "jpeg", "png", "webp", "avif", "svg"]
WAGTAILIMAGES_MAX_UPLOAD_SIZE = 15 * 1024 * 1024
WAGTAILDOCS_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "csv", "txt", "zip"]
WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}
WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAILADMIN_PERMITTED_LANGUAGES = [("en", "English")]
WAGTAIL_PASSWORD_RESET_ENABLED = True
WAGTAILEMBEDS_RESPONSIVE_HTML = True
WAGTAILADMIN_COMMENTS_ENABLED = True

# Path of the owner/staff admin. Change ADMIN_PATH in .env to move it somewhere less guessable.
ADMIN_PATH = os.environ.get("ADMIN_PATH", "admin").strip("/")
# Raw Django admin, kept only as a superuser emergency fallback.
DJANGO_ADMIN_PATH = os.environ.get("DJANGO_ADMIN_PATH", "django-admin-fallback").strip("/")
# Require a 2FA code for admin access. Turn off only for local development.
ADMIN_REQUIRE_2FA = env_bool("ADMIN_REQUIRE_2FA", True)

# --- Accounts (public supporters) ------------------------------------------
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "account_dashboard"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = os.environ.get("ACCOUNT_EMAIL_VERIFICATION", "mandatory")
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_SIGNUP_FORM_CLASS = "apps.accounts.forms.SupporterSignupForm"
ACCOUNT_RATE_LIMITS = {"login_failed": "10/m/ip,5/5m/key"}
ACCOUNT_ADAPTER = "apps.accounts.adapter.SupporterAccountAdapter"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True

# --- Email -----------------------------------------------------------------
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Haven Medical Relief <no-reply@example.org>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- Celery ----------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "send-due-ecards": {"task": "apps.giving.tasks.send_due_ecards", "schedule": 300.0},
    "daily-housekeeping": {"task": "apps.involvement.tasks.daily_housekeeping", "schedule": 60 * 60 * 6},
}

# --- Payments --------------------------------------------------------------
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
# Offline fake provider for local development and tests (never enable in production).
PAYMENTS_FAKE_MODE = env_bool("PAYMENTS_FAKE_MODE", False)

# --- Newsletter (Brevo) ----------------------------------------------------
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_LIST_ID = os.environ.get("BREVO_LIST_ID", "")

# --- Spam protection -------------------------------------------------------
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")
RATELIMIT_VIEW = "apps.core.views.ratelimited"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {
        "django_tasks": {"level": "WARNING"},
        "wagtail": {"level": "WARNING"},
    },
}
WAGTAILIMAGES_IMAGE_FORM_BASE = "apps.core.forms.CustomImageForm"
