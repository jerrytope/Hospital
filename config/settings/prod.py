import os

from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = False
PAYMENTS_FAKE_MODE = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
# Only turn these off while the site is served over plain HTTP (no domain/HTTPS yet).
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
# SAMEORIGIN (not DENY) because the Wagtail editor previews pages in a same-site frame.
X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]

if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {  # noqa: F405
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["AWS_STORAGE_BUCKET_NAME"],
            "custom_domain": os.environ.get("AWS_S3_CUSTOM_DOMAIN") or None,
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL") or None,
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": False,
        },
    }

if os.environ.get("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0.1, send_default_pii=False)
