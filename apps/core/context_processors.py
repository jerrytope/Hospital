from django.conf import settings


def site_context(request):
    return {
        "SITE_URL": settings.SITE_URL,
        "TURNSTILE_SITE_KEY": settings.TURNSTILE_SITE_KEY,
        "cookie_consent": request.COOKIES.get("cookie_consent", ""),
    }
