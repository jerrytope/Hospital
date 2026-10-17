from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = True
ALLOWED_HOSTS = ["*"]
# Emails are saved as files in sent-emails/ so you can open receipts and e-cards locally.
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = BASE_DIR / "sent-emails"  # noqa: F405
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
PAYMENTS_FAKE_MODE = env_bool("PAYMENTS_FAKE_MODE", True)
ADMIN_REQUIRE_2FA = env_bool("ADMIN_REQUIRE_2FA", False)
ACCOUNT_EMAIL_VERIFICATION = "optional"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
