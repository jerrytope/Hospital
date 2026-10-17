import logging

from celery import shared_task
from django.utils import timezone

from .emails import send_templated

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=120)
def send_receipt(self, donation_id):
    from .models import Donation
    from .receipts import receipt_pdf

    donation = Donation.objects.select_related("emergency", "fundraiser", "recurring_gift").get(pk=donation_id)
    if donation.status != "succeeded" or donation.receipt_sent_at:
        return
    try:
        pdf, filename = receipt_pdf(donation)
        send_templated(
            donation.email,
            f"Thank you for your gift — receipt {donation.receipt.display_number}",
            "receipt",
            {"donation": donation},
            attachments=[(filename, pdf, "application/pdf")],
        )
    except Exception as exc:
        log.exception("Receipt email failed for %s", donation)
        raise self.retry(exc=exc)
    Donation.objects.filter(pk=donation.pk).update(receipt_sent_at=timezone.now())
    if donation.fundraiser_id:
        notify_fundraiser_owner.delay(donation.pk)


@shared_task
def notify_fundraiser_owner(donation_id):
    from .models import Donation

    d = Donation.objects.select_related("fundraiser__owner").get(pk=donation_id)
    owner = d.fundraiser.owner
    send_templated(owner.email, f"New gift to “{d.fundraiser.title}”", "fundraiser_gift", {"donation": d, "fundraiser": d.fundraiser})


@shared_task
def send_due_ecards():
    """Runs every 5 minutes: send paid e-cards whose send time has arrived."""
    from .models import ECard

    due = ECard.objects.filter(status="scheduled", send_at__lte=timezone.now()).select_related("donation", "gift_order")
    sent = 0
    for card in due:
        if not card.is_paid:
            continue
        send_ecard(card.pk)
        sent += 1
    return sent


@shared_task
def send_ecard(ecard_id):
    from .models import ECard

    card = ECard.objects.select_related("donation", "gift_order").get(pk=ecard_id)
    if card.status != "scheduled" or not card.is_paid:
        return
    card.attempts += 1
    try:
        subject = f"{card.sender_name} sent you a card"
        if card.card_type == "memory":
            subject = f"A gift in memory of {card.honoree_name}"
        elif card.card_type == "honor":
            subject = f"A gift in honour of {card.honoree_name or card.recipient_name}"
        send_templated(card.recipient_email, subject, "ecard", {"card": card})
        card.status = "sent"
        card.sent_at = timezone.now()
        card.failure_reason = ""
    except Exception as exc:
        log.exception("E-card %s failed", card.pk)
        card.failure_reason = str(exc)[:500]
        if card.attempts >= 5:
            card.status = "failed"
    card.save()


@shared_task
def send_payment_failed_notice(recurring_id):
    from .models import RecurringGift

    r = RecurringGift.objects.get(pk=recurring_id)
    send_templated(r.email, "We couldn't process your monthly gift", "payment_failed", {"recurring": r})


@shared_task
def send_bank_notice_received(notice_id):
    from .models import BankTransferNotice, DonationSettings

    n = BankTransferNotice.objects.get(pk=notice_id)
    send_templated(n.email, "We've received your bank transfer details", "bank_notice_received", {"notice": n})
    ds = DonationSettings.load()
    if ds.notify_email:
        from django.conf import settings

        send_templated(
            ds.notify_email,
            f"New bank transfer notice {n.reference} ({n.display_amount})",
            "staff_bank_notice",
            {"notice": n, "admin_url": f"{settings.SITE_URL}/{settings.ADMIN_PATH}/bank-transfers/"},
        )


@shared_task
def send_bank_notice_rejected(notice_id):
    from .models import BankTransferNotice

    n = BankTransferNotice.objects.get(pk=notice_id)
    send_templated(n.email, "About your bank transfer", "bank_notice_rejected", {"notice": n})


@shared_task
def notify_bank_details_changed(account_label, action, staff_email):
    from apps.core.models import OrganisationSettings

    from .models import DonationSettings

    ds = DonationSettings.load()
    org = OrganisationSettings.load()
    to = ds.notify_email or org.general_email
    if not to:
        return
    send_templated(
        to,
        f"Security notice: bank details {action}",
        "staff_bank_changed",
        {"account_label": account_label, "action": action, "staff_email": staff_email, "when": timezone.now()},
    )
