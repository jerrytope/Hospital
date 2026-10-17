"""Cloudflare Turnstile check. Passes automatically when no secret key is configured."""
import requests
from django.conf import settings


def turnstile_ok(request):
    if not settings.TURNSTILE_SECRET_KEY:
        return True
    token = request.POST.get("cf-turnstile-response", "")
    if not token:
        return False
    try:
        resp = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": settings.TURNSTILE_SECRET_KEY, "response": token, "remoteip": request.META.get("REMOTE_ADDR")},
            timeout=10,
        )
        return bool(resp.json().get("success"))
    except (requests.RequestException, ValueError):
        return False
