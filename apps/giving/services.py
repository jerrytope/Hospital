"""All donation state changes go through here, so webhooks, the admin and the account
area share one set of rules."""
import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Appeal, BankTransferNotice, Donation, ECard, GiftOrder, Receipt, RecurringGift

log = logging.getLogger(__name__)


def resolve_appeal(code):
    """Find the Appeal for a code, creating a flagged placeholder for unknown codes."""
    code = (code or "").strip().upper()[:40]
    if not code:
        return None
    appeal, _ = Appeal.objects.get_or_create(
        code=code, defaults={"name": f"Unregistered code {code}", "auto_created": True}
    )
    return appeal


def find_user_for_email(email):
    """Attach gifts to an account only when that email address has been verified."""
    from allauth.account.models import EmailAddress

    addr = EmailAddress.objects.filter(email__iexact=email, verified=True).select_related("user").first()
    return addr.user if addr else None


@transaction.atomic
def create_donation(*, amount, currency, frequency, provider, donor, appeal_code="", emergency=None,
                    fundraiser=None, source_url="", user=None, tribute=None, display_name="",
                    is_anonymous=False, public_message=""):
    """Create a pending donation (and its monthly gift / tribute e-card) before checkout."""
    appeal = resolve_appeal(appeal_code)
    if appeal and appeal.emergency_id and not emergency:
        emergency = appeal.emergency
    if fundraiser and fundraiser.emergency_id and not emergency:
        emergency = fundraiser.emergency
    user = user if (user and user.is_authenticated) else None

    recurring = None
    if frequency == "monthly":
        recurring = RecurringGift.objects.create(
            user=user,
            email=donor["email"],
            first_name=donor["first_name"],
            last_name=donor["last_name"],
            amount=amount,
            currency=currency,
            provider=provider,
            appeal_code=appeal.code if appeal else "",
            emergency=emergency,
            day_of_month=timezone.localdate().day,
        )

    donation = Donation.objects.create(
        amount=amount,
        currency=currency,
        frequency=frequency,
        provider=provider,
        first_name=donor["first_name"],
        last_name=donor["last_name"],
        email=donor["email"],
        phone=donor.get("phone", ""),
        user=user,
        appeal_code=appeal.code if appeal else "",
        appeal=appeal,
        emergency=emergency,
        fundraiser=fundraiser,
        recurring_gift=recurring,
        source_url=source_url[:500],
        display_name=display_name,
        is_anonymous=is_anonymous,
        public_message=public_message,
    )
    if tribute:
        ECard.objects.create(donation=donation, **tribute)
    return donation


def donation_succeeded(donation, provider_reference=None, when=None):
    """Mark paid, then issue the receipt and release any e-cards. Safe to call twice."""
    if not donation.mark_succeeded(provider_reference=provider_reference, when=when):
        return False
    if not donation.user_id:
        user = find_user_for_email(donation.email)
        if user:
            donation.user = user
            donation.save(update_fields=["user"])
            if donation.recurring_gift_id:
                RecurringGift.objects.filter(pk=donation.recurring_gift_id, user__isnull=True).update(user=user)
    if donation.recurring_gift_id:
        RecurringGift.objects.filter(pk=donation.recurring_gift_id, status="pending").update(status="active")
    order = GiftOrder.objects.filter(donation=donation).first()
    if order and order.status != "paid":
        order.status = "paid"
        order.save(update_fields=["status"])
    Receipt.for_donation(donation)
    _after_commit_send_receipt(donation.pk)
    _after_commit_send_due_ecards(donation, order)
    return True


def _after_commit_send_due_ecards(donation, order=None):
    """E-cards due now go out as soon as the gift is paid; later ones wait for the scheduler."""
    from .tasks import send_ecard

    cards = ECard.objects.filter(status="scheduled", send_at__lte=timezone.now())
    cards = cards.filter(gift_order=order) if order else cards.filter(donation=donation)
    for card_id in cards.values_list("pk", flat=True):
        transaction.on_commit(lambda cid=card_id: send_ecard.delay(cid), robust=True)


def _after_commit_send_receipt(donation_id):
    from .tasks import send_receipt

    transaction.on_commit(lambda: send_receipt.delay(donation_id), robust=True)


def record_renewal(recurring, amount, provider_reference="", when=None):
    """A monthly charge succeeded: record it as its own donation with a receipt."""
    if provider_reference and Donation.objects.filter(
        provider=recurring.provider, provider_reference=provider_reference
    ).exists():
        return None
    donation = Donation.objects.create(
        amount=Decimal(amount),
        currency=recurring.currency,
        frequency="monthly",
        provider=recurring.provider,
        first_name=recurring.first_name,
        last_name=recurring.last_name,
        email=recurring.email,
        user=recurring.user,
        appeal_code=recurring.appeal_code,
        appeal=resolve_appeal(recurring.appeal_code),
        emergency=recurring.emergency,
        recurring_gift=recurring,
    )
    donation_succeeded(donation, provider_reference=provider_reference, when=when)
    if recurring.status in ("past_due", "pending"):
        recurring.status = "active"
        recurring.save(update_fields=["status"])
    return donation


def recurring_payment_failed(recurring):
    recurring.status = "past_due"
    recurring.save(update_fields=["status"])
    from .tasks import send_payment_failed_notice

    transaction.on_commit(lambda: send_payment_failed_notice.delay(recurring.pk), robust=True)


def mark_recurring_cancelled(recurring):
    recurring.status = "cancelled"
    recurring.cancelled_at = timezone.now()
    recurring.save(update_fields=["status", "cancelled_at"])


def donation_refunded(donation, note=""):
    if donation.status == "refunded":
        return
    donation.status = "refunded"
    donation.refunded_at = timezone.now()
    if note:
        donation.admin_notes = (donation.admin_notes + "\n" + note).strip()
    donation.save(update_fields=["status", "refunded_at", "admin_notes"])
    ECard.objects.filter(donation=donation, status="scheduled").update(status="cancelled")


# --- Bank transfers ------------------------------------------------------------


@transaction.atomic
def confirm_bank_notice(notice, staff_user, amount=None):
    """Owner confirms money arrived: create a succeeded donation and send the receipt."""
    notice = BankTransferNotice.objects.select_for_update().get(pk=notice.pk)
    if notice.status == "confirmed":
        return notice.donation
    appeal = resolve_appeal(notice.appeal_code or "BANK-TRANSFER")
    donation = Donation.objects.create(
        amount=amount or notice.amount,
        currency=notice.currency,
        frequency="one_time",
        provider="bank",
        provider_reference=notice.bank_reference or notice.reference,
        first_name=notice.first_name,
        last_name=notice.last_name,
        email=notice.email,
        phone=notice.phone,
        user=notice.user,
        appeal_code=appeal.code if appeal else "",
        appeal=appeal,
        emergency=notice.emergency,
        fundraiser=notice.fundraiser,
        admin_notes=f"Bank transfer notice {notice.reference} confirmed by {staff_user}",
    )
    donation_succeeded(donation, provider_reference=donation.provider_reference)
    notice.status = "confirmed"
    notice.donation = donation
    notice.reviewed_by = staff_user
    notice.reviewed_at = timezone.now()
    notice.save()
    return donation


def reject_bank_notice(notice, staff_user, reason):
    notice.status = "rejected"
    notice.rejection_reason = reason
    notice.reviewed_by = staff_user
    notice.reviewed_at = timezone.now()
    notice.save()
    from .tasks import send_bank_notice_rejected

    transaction.on_commit(lambda: send_bank_notice_rejected.delay(notice.pk), robust=True)


# --- Account linking ---------------------------------------------------------------


def claim_gifts_for_user(user):
    """After a supporter verifies their email, attach their earlier guest gifts."""
    email = user.email
    Donation.objects.filter(user__isnull=True, email__iexact=email).update(user=user)
    RecurringGift.objects.filter(user__isnull=True, email__iexact=email).update(user=user)
    GiftOrder.objects.filter(user__isnull=True, email__iexact=email).update(user=user)
    BankTransferNotice.objects.filter(user__isnull=True, email__iexact=email).update(user=user)


def anonymise_user(user):
    """Account deletion: remove personal data but keep financial records for the books."""
    User = get_user_model()
    placeholder = f"deleted-{user.pk}@deleted.invalid"
    Donation.objects.filter(user=user).update(
        user=None, first_name="Deleted", last_name="Supporter", email=placeholder, phone="", display_name=""
    )
    RecurringGift.objects.filter(user=user).update(user=None, first_name="Deleted", last_name="Supporter", email=placeholder)
    GiftOrder.objects.filter(user=user).update(user=None, first_name="Deleted", last_name="Supporter", email=placeholder)
    from apps.newsletter.models import Subscriber

    Subscriber.objects.filter(email__iexact=user.email).delete()
    User.objects.filter(pk=user.pk).delete()
