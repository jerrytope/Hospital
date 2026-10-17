import io
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.giving import services
from apps.giving.models import ECard
from apps.payments.models import WebhookEvent

pytestmark = pytest.mark.django_db


def paid(user, **extra):
    d = services.create_donation(
        amount=Decimal("10000"), currency="NGN", frequency=extra.pop("frequency", "one_time"), provider="fake",
        donor={"first_name": user.first_name, "last_name": user.last_name, "email": user.email}, user=user, **extra,
    )
    services.donation_succeeded(d)
    d.refresh_from_db()
    return d


def test_data_export(client, home, supporter):
    paid(supporter)
    client.force_login(supporter)
    resp = client.get(reverse("account_export"))
    data = json.loads(resp.content)
    assert data["account"]["email"] == supporter.email and len(data["donations"]) == 1


def test_owner_cancels_monthly_gift_on_donors_behalf(client, home, owner, supporter, settings):
    settings.ADMIN_REQUIRE_2FA = False
    gift = paid(supporter, frequency="monthly").recurring_gift
    client.force_login(owner)
    assert client.get(f"/admin/monthly_gifts/inspect/{gift.pk}/").status_code == 200
    client.post(reverse("dashboard_recurring_action", args=[gift.pk]), {"action": "cancel"})
    gift.refresh_from_db()
    assert gift.status == "cancelled"


def test_failed_webhook_can_be_retried(client, home, owner, settings, monkeypatch):
    from apps.payments import handlers

    settings.ADMIN_REQUIRE_2FA = False
    d = services.create_donation(amount=Decimal("5000"), currency="NGN", frequency="one_time", provider="fake",
                                 donor={"first_name": "A", "last_name": "B", "email": "a@b.org"})
    original = handlers.HANDLERS["fake"]["payment.succeeded"]
    monkeypatch.setitem(handlers.HANDLERS["fake"], "payment.succeeded", lambda payload: 1 / 0)
    event = handlers.record_and_handle("fake", "evt_x", "payment.succeeded", {"reference": d.reference})
    assert "ZeroDivisionError" in event.error
    monkeypatch.setitem(handlers.HANDLERS["fake"], "payment.succeeded", original)
    client.force_login(owner)
    client.post(reverse("dashboard_webhook_retry", args=[event.pk]))
    event.refresh_from_db()
    d.refresh_from_db()
    assert event.error == "" and d.status == "succeeded"
    assert WebhookEvent.objects.count() == 1


def test_fundraiser_photo_is_resized_and_stripped_of_metadata(client, home, supporter):
    from PIL import Image

    from apps.fundraising.models import Fundraiser

    img = Image.new("RGB", (3000, 2000), "red")
    exif = Image.Exif()
    exif[0x010F] = "TrackingCam"  # camera make: any metadata must be dropped
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    upload = SimpleUploadedFile("me.jpg", buf.getvalue(), content_type="image/jpeg")
    client.force_login(supporter)
    resp = client.post(reverse("account_fundraiser_create"), {
        "title": "Photo test", "story": "x", "goal": "1000", "currency": "NGN", "photo": upload})
    assert resp.status_code == 302
    saved = Image.open(Fundraiser.objects.get().photo.path)
    assert max(saved.size) <= 1800
    assert len(saved.getexif()) == 0


def test_future_ecard_waits_for_its_date(home, supporter):
    from apps.giving.tasks import send_due_ecards

    later = timezone.now() + timedelta(days=3)
    d = paid(supporter, tribute={"card_type": "memory", "honoree_name": "Grandpa", "sender_name": "Ada Obi",
                                 "recipient_name": "Mum", "recipient_email": "mum@test.org", "send_at": later})
    card = d.ecards.get()
    send_due_ecards()
    card.refresh_from_db()
    assert card.status == "scheduled"
    ECard.objects.filter(pk=card.pk).update(send_at=timezone.now() - timedelta(minutes=1))
    send_due_ecards()
    card.refresh_from_db()
    assert card.status == "sent"
