from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.giving import services
from apps.giving.models import Appeal, BankAccount, BankTransferNotice, Donation, ECard, Receipt, RecurringGift
from apps.payments.handlers import record_and_handle
from apps.payments.models import WebhookEvent

pytestmark = pytest.mark.django_db


def pay(client, data):
    """Start checkout and approve it on the offline test checkout page."""
    resp = client.post(reverse("giving:checkout"), data)
    assert resp.status_code == 302, resp.content[:500]
    donation = Donation.objects.latest("created_at")
    assert resp["Location"] == reverse("payments:fake_checkout", args=[donation.reference])
    resp = client.post(resp["Location"], {"outcome": "pay"})
    assert resp.status_code == 302
    donation.refresh_from_db()
    return donation


def test_one_time_donation_succeeds_with_receipt_and_appeal(client, home, donation_data):
    donation = pay(client, donation_data)
    assert donation.status == "succeeded"
    assert donation.amount == Decimal("25000")
    assert donation.appeal_code == "HOME-HERO"
    assert Appeal.objects.get(code="HOME-HERO").auto_created
    assert Receipt.objects.filter(donation=donation).exists()
    assert donation.receipt_sent_at is not None
    assert any(m.attachments for m in mail.outbox if donation.email in m.to)
    # Return page shows thank you for the browser that paid
    page = client.get(reverse("giving:return", args=[donation.reference]))
    assert b"Thank you" in page.content


def test_return_page_hidden_from_other_browsers(client, home, donation_data):
    donation = pay(client, donation_data)
    from django.test import Client

    assert Client().get(reverse("giving:return", args=[donation.reference])).status_code == 404


def test_below_minimum_is_rejected(client, home, donation_data):
    donation_data["amount"] = "50"
    resp = client.post(reverse("giving:checkout"), donation_data)
    assert resp.status_code == 400
    assert not Donation.objects.exists()


def test_emergency_donation_is_tagged(client, emergency, donation_data):
    donation_data.update({"emergency": emergency.pk, "appeal_code": ""})
    donation = pay(client, donation_data)
    assert donation.emergency == emergency


def test_duplicate_webhook_is_processed_once(home):
    donation = services.create_donation(
        amount=Decimal("5000"), currency="NGN", frequency="one_time", provider="fake",
        donor={"first_name": "A", "last_name": "B", "email": "a@b.org"},
    )
    payload = {"id": "evt_1", "type": "payment.succeeded", "reference": donation.reference}
    record_and_handle("fake", "evt_1", "payment.succeeded", payload)
    record_and_handle("fake", "evt_1", "payment.succeeded", payload)
    assert WebhookEvent.objects.count() == 1
    assert Receipt.objects.count() == 1
    assert len([m for m in mail.outbox if "a@b.org" in m.to]) == 1


def test_failed_payment(client, home, donation_data):
    client.post(reverse("giving:checkout"), donation_data)
    donation = Donation.objects.get()
    client.post(reverse("payments:fake_checkout", args=[donation.reference]), {"outcome": "decline"})
    donation.refresh_from_db()
    assert donation.status == "failed"
    assert not Receipt.objects.exists()


def test_monthly_gift_and_renewal(client, home, donation_data):
    donation_data["frequency"] = "monthly"
    donation = pay(client, donation_data)
    gift = donation.recurring_gift
    gift.refresh_from_db()
    assert gift.status == "active"
    renewal = services.record_renewal(gift, gift.amount, provider_reference="ren-1")
    assert renewal.status == "succeeded" and renewal.recurring_gift == gift
    # Same provider reference again does nothing
    assert services.record_renewal(gift, gift.amount, provider_reference="ren-1") is None
    assert gift.charges.filter(status="succeeded").count() == 2


def test_guest_gift_attaches_to_verified_account(client, home, supporter, donation_data):
    donation = pay(client, donation_data)
    assert donation.user == supporter


def test_bank_transfer_notice_confirm_creates_donation(client, home, owner):
    account = BankAccount.objects.create(bank_name="Sample Bank", account_name="Charity", account_number="0123456789", currency="NGN")
    resp = client.post(reverse("giving:bank_notice"), {
        "first_name": "Chi", "last_name": "Eze", "email": "chi@test.org", "amount": "30000", "currency": "NGN",
        "bank_account": account.pk, "transfer_date": timezone.localdate().isoformat(), "bank_reference": "GIFT-1",
        "consent": "on", "appeal_code": "",
    })
    assert resp.status_code == 200 and b"Thank you" in resp.content
    notice = BankTransferNotice.objects.get()
    assert notice.status == "pending"
    donation = services.confirm_bank_notice(notice, owner)
    notice.refresh_from_db()
    assert notice.status == "confirmed" and notice.donation == donation
    assert donation.status == "succeeded" and donation.provider == "bank"
    assert Receipt.objects.filter(donation=donation).exists()
    # Confirming twice does not double count
    assert services.confirm_bank_notice(notice, owner) == donation
    assert Donation.objects.filter(provider="bank").count() == 1


def test_bank_notice_rejects_future_date(client, home):
    resp = client.post(reverse("giving:bank_notice"), {
        "first_name": "Chi", "last_name": "Eze", "email": "chi@test.org", "amount": "30000", "currency": "NGN",
        "transfer_date": (timezone.localdate() + timedelta(days=2)).isoformat(), "consent": "on",
    })
    assert b"cannot be in the future" in resp.content
    assert not BankTransferNotice.objects.exists()


def test_bank_accounts_show_on_donate_page(client, home):
    BankAccount.objects.create(bank_name="Sample Bank", account_name="Charity", account_number="9988776655", currency="NGN")
    BankAccount.objects.create(bank_name="Hidden Bank", account_name="Charity", account_number="1111111111", currency="NGN", active=False)
    content = client.get(reverse("giving:donate")).content
    assert b"9988776655" in content
    assert b"1111111111" not in content


def test_tribute_ecard_sent_only_after_payment(client, home, donation_data):
    donation_data.update({"tribute": "on", "card_type": "memory", "honoree_name": "Mama Nkechi",
                          "recipient_name": "Uche", "recipient_email": "uche@test.org", "message": "Thinking of you"})
    client.post(reverse("giving:checkout"), donation_data)
    card = ECard.objects.get()
    from apps.giving.tasks import send_due_ecards

    send_due_ecards()
    card.refresh_from_db()
    assert card.status == "scheduled"  # unpaid
    donation = Donation.objects.get()
    client.post(reverse("payments:fake_checkout", args=[donation.reference]), {"outcome": "pay"})
    send_due_ecards()
    card.refresh_from_db()
    assert card.status == "sent"
    assert any("uche@test.org" in m.to and "Mama Nkechi" in m.subject for m in mail.outbox)


def test_refund_cancels_scheduled_ecards(home):
    donation = services.create_donation(
        amount=Decimal("5000"), currency="NGN", frequency="one_time", provider="fake",
        donor={"first_name": "A", "last_name": "B", "email": "a@b.org"},
        tribute={"card_type": "honor", "honoree_name": "X", "sender_name": "A B", "recipient_name": "Y",
                 "recipient_email": "y@b.org", "send_at": timezone.now() + timedelta(days=3)},
    )
    services.donation_succeeded(donation)
    services.donation_refunded(donation)
    assert ECard.objects.get().status == "cancelled"
    assert Donation.objects.get().status == "refunded"


def test_gift_catalog_checkout(client, home):
    from apps.giving.models import GiftItem, GiftOrder

    item = GiftItem.objects.create(title="Medical kit", price_ngn=Decimal("25000"), price_usd=Decimal("25"), blurb="x")
    client.post(reverse("giving:cart_update"), {"item": item.pk, "action": "add"})
    client.post(reverse("giving:cart_update"), {"item": item.pk, "action": "add"})
    resp = client.post(reverse("giving:gift_checkout"), {
        "first_name": "Ada", "last_name": "Obi", "email": "ada@test.org", "send_ecard": "on",
        "recipient_name": "Bola", "recipient_email": "bola@test.org", "message": "For you",
    })
    assert resp.status_code == 302
    order = GiftOrder.objects.get()
    assert order.total == Decimal("50000")
    client.post(resp["Location"], {"outcome": "pay"})
    order.refresh_from_db()
    assert order.status == "paid"
    assert ECard.objects.get().status == "sent"
