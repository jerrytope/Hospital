"""Turn verified provider events into donation state changes.

Each handler is idempotent: the WebhookEvent table blocks duplicate deliveries, and
Donation.mark_succeeded only acts on the first transition.
"""
import logging
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.giving import services
from apps.giving.models import Donation, RecurringGift

from .models import WebhookEvent

log = logging.getLogger(__name__)


def record_and_handle(provider, event_id, event_type, payload):
    """Store the event and process it once. Returns the WebhookEvent."""
    try:
        with transaction.atomic():
            event = WebhookEvent.objects.create(
                provider=provider, event_id=event_id, event_type=event_type, payload=payload
            )
    except IntegrityError:
        event = WebhookEvent.objects.get(provider=provider, event_id=event_id)
        if event.processed_at and not event.error:
            return event  # duplicate delivery of an event we already handled
    process_event(event)
    return event


def process_event(event):
    handler = HANDLERS.get(event.provider, {}).get(event.event_type)
    try:
        with transaction.atomic():
            if handler:
                handler(event.payload)
        event.error = ""
    except Exception as exc:  # recorded for the admin webhook log and retried from there
        log.exception("Webhook %s failed", event)
        event.error = f"{type(exc).__name__}: {exc}"
    event.processed_at = timezone.now()
    event.save(update_fields=["processed_at", "error"])
    return event


# --- Paystack -------------------------------------------------------------------------


def _paystack_charge_success(payload):
    data = payload["data"]
    reference = data.get("reference", "")
    amount = Decimal(data.get("amount", 0)) / 100
    paid_at = _parse_iso(data.get("paid_at"))
    customer = data.get("customer") or {}
    authorization = (data.get("authorization") or {}).get("authorization_code", "")
    donation = Donation.objects.select_for_update().filter(reference=reference).first()
    if donation:
        if donation.recurring_gift_id and authorization:
            RecurringGift.objects.filter(pk=donation.recurring_gift_id).update(
                provider_authorization=authorization, provider_customer_id=customer.get("customer_code", "")
            )
        services.donation_succeeded(donation, provider_reference=str(data.get("id", "")), when=paid_at)
        return
    # A renewal: Paystack generates its own reference for subscription charges.
    plan = data.get("plan") or {}
    plan_code = plan.get("plan_code") if isinstance(plan, dict) else ""
    recurring = RecurringGift.objects.filter(provider="paystack", provider_plan=plan_code).first() if plan_code else None
    if recurring:
        services.record_renewal(recurring, amount, provider_reference=str(data.get("id", "")), when=paid_at)


def _paystack_subscription_create(payload):
    data = payload["data"]
    plan_code = (data.get("plan") or {}).get("plan_code", "")
    recurring = RecurringGift.objects.filter(provider="paystack", provider_plan=plan_code).first()
    if not recurring:
        return
    recurring.provider_subscription_id = data.get("subscription_code", "")
    recurring.provider_token = data.get("email_token", "")
    recurring.provider_customer_id = (data.get("customer") or {}).get("customer_code", "") or recurring.provider_customer_id
    if (data.get("authorization") or {}).get("authorization_code"):
        recurring.provider_authorization = data["authorization"]["authorization_code"]
    if data.get("next_payment_date"):
        recurring.next_charge_date = data["next_payment_date"][:10]
    if recurring.status in ("pending", "past_due"):
        recurring.status = "active"
    recurring.save()


def _paystack_subscription_disable(payload):
    code = payload["data"].get("subscription_code", "")
    recurring = RecurringGift.objects.filter(provider="paystack", provider_subscription_id=code).first()
    # Pauses and changes also disable the old subscription; only mark cancelled if we didn't ask for it.
    if recurring and recurring.status == "active":
        services.mark_recurring_cancelled(recurring)


def _paystack_payment_failed(payload):
    code = (payload["data"].get("subscription") or {}).get("subscription_code", "")
    recurring = RecurringGift.objects.filter(provider="paystack", provider_subscription_id=code).first()
    if recurring:
        services.recurring_payment_failed(recurring)


def _paystack_refund(payload):
    data = payload["data"]
    ref = data.get("transaction_reference") or (data.get("transaction") or {}).get("reference", "")
    donation = Donation.objects.filter(reference=ref).first()
    if donation:
        services.donation_refunded(donation)


# --- Stripe ---------------------------------------------------------------------------


def _stripe_checkout_completed(payload):
    session = payload["data"]["object"]
    reference = session.get("client_reference_id") or (session.get("metadata") or {}).get("donation_reference")
    donation = Donation.objects.select_for_update().filter(reference=reference).first()
    if not donation:
        return
    if session.get("mode") == "subscription":
        if donation.recurring_gift_id:
            RecurringGift.objects.filter(pk=donation.recurring_gift_id).update(
                provider_subscription_id=session.get("subscription") or "",
                provider_customer_id=session.get("customer") or "",
                status="active",
            )
        if session.get("payment_status") == "paid":
            services.donation_succeeded(donation, provider_reference=session.get("invoice") or session.get("id"))
    elif session.get("payment_status") == "paid":
        services.donation_succeeded(donation, provider_reference=session.get("payment_intent") or session.get("id"))


def _stripe_invoice_paid(payload):
    invoice = payload["data"]["object"]
    if invoice.get("billing_reason") != "subscription_cycle":
        return  # the first invoice is covered by checkout.session.completed
    sub_id = invoice.get("subscription") or (
        ((invoice.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    )
    recurring = RecurringGift.objects.filter(provider="stripe", provider_subscription_id=sub_id).first()
    if recurring:
        amount = Decimal(invoice.get("amount_paid", 0)) / 100
        when = datetime.fromtimestamp(invoice.get("created", 0), tz=dt_timezone.utc) if invoice.get("created") else None
        services.record_renewal(recurring, amount, provider_reference=invoice.get("id"), when=when)


def _stripe_invoice_failed(payload):
    invoice = payload["data"]["object"]
    sub_id = invoice.get("subscription") or (
        ((invoice.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    )
    recurring = RecurringGift.objects.filter(provider="stripe", provider_subscription_id=sub_id).first()
    if recurring:
        services.recurring_payment_failed(recurring)


def _stripe_subscription_deleted(payload):
    sub = payload["data"]["object"]
    recurring = RecurringGift.objects.filter(provider="stripe", provider_subscription_id=sub.get("id")).first()
    if recurring and recurring.status != "cancelled":
        services.mark_recurring_cancelled(recurring)


def _stripe_charge_refunded(payload):
    charge = payload["data"]["object"]
    donation = Donation.objects.filter(provider_reference=charge.get("payment_intent")).first()
    if donation:
        services.donation_refunded(donation)


# --- Fake (local development) ---------------------------------------------------------


def _fake_payment_succeeded(payload):
    donation = Donation.objects.select_for_update().filter(reference=payload["reference"]).first()
    if not donation:
        return
    if donation.recurring_gift_id:
        RecurringGift.objects.filter(pk=donation.recurring_gift_id).update(
            provider_subscription_id=f"fake_sub_{donation.reference}", status="active"
        )
    services.donation_succeeded(donation, provider_reference=f"fake_{donation.reference}")


def _fake_payment_failed(payload):
    donation = Donation.objects.filter(reference=payload["reference"]).first()
    if donation and donation.status == "pending":
        donation.status = "failed"
        donation.save(update_fields=["status"])


def _fake_renewal(payload):
    recurring = RecurringGift.objects.filter(reference=payload["recurring_reference"]).first()
    if recurring:
        services.record_renewal(recurring, recurring.amount, provider_reference=payload["id"])


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


HANDLERS = {
    "paystack": {
        "charge.success": _paystack_charge_success,
        "subscription.create": _paystack_subscription_create,
        "subscription.disable": _paystack_subscription_disable,
        "subscription.not_renew": _paystack_subscription_disable,
        "invoice.payment_failed": _paystack_payment_failed,
        "refund.processed": _paystack_refund,
    },
    "stripe": {
        "checkout.session.completed": _stripe_checkout_completed,
        "checkout.session.async_payment_succeeded": _stripe_checkout_completed,
        "invoice.paid": _stripe_invoice_paid,
        "invoice.payment_failed": _stripe_invoice_failed,
        "customer.subscription.deleted": _stripe_subscription_deleted,
        "charge.refunded": _stripe_charge_refunded,
    },
    "fake": {
        "payment.succeeded": _fake_payment_succeeded,
        "payment.failed": _fake_payment_failed,
        "subscription.renewed": _fake_renewal,
    },
}
