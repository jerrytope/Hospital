from .dev import *  # noqa: F401,F403

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
PAYMENTS_FAKE_MODE = True
ADMIN_REQUIRE_2FA = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
RATELIMIT_ENABLE = False
MEDIA_ROOT = BASE_DIR / "test-media"  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
