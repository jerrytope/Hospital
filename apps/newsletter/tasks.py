import logging

import requests
from celery import shared_task
from django.conf import settings

log = logging.getLogger(__name__)

BREVO_CONTACTS = "https://api.brevo.com/v3/contacts"


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_subscriber(self, subscriber_id):
    """Push a subscribe/unsubscribe to Brevo. Skipped (and marked so) when Brevo isn't configured."""
    from .models import Subscriber

    sub = Subscriber.objects.filter(pk=subscriber_id).first()
    if not sub:
        return
    if not settings.BREVO_API_KEY:
        Subscriber.objects.filter(pk=sub.pk).update(sync_status="skipped", sync_error="")
        return
    payload = {
        "email": sub.email,
        "attributes": {"FIRSTNAME": sub.first_name, "LASTNAME": sub.last_name},
        "updateEnabled": True,
        "emailBlacklisted": sub.status == "unsubscribed",
    }
    if settings.BREVO_LIST_ID:
        payload["listIds"] = [int(settings.BREVO_LIST_ID)]
    try:
        resp = requests.post(
            BREVO_CONTACTS,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
            timeout=15,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Brevo {resp.status_code}: {resp.text[:300]}")
    except Exception as exc:
        Subscriber.objects.filter(pk=sub.pk).update(sync_status="failed", sync_error=str(exc)[:500])
        raise self.retry(exc=exc)
    Subscriber.objects.filter(pk=sub.pk).update(sync_status="synced", sync_error="")
