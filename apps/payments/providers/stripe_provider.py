"""Stripe (USD): Checkout for one-time and monthly gifts, Billing for subscription changes."""
import json
from datetime import datetime, time
from decimal import Decimal

import stripe
from django.conf import settings
from django.utils import timezone

from .base import PaymentError, Provider


def to_cents(amount):
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


class StripeProvider(Provider):
    name = "stripe"

    def __init__(self):
        if not settings.STRIPE_SECRET_KEY:
            raise PaymentError("Stripe is not configured (STRIPE_SECRET_KEY is empty)")
        self.client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)

    def _wrap(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except stripe.StripeError as exc:
            raise PaymentError(f"Stripe error: {getattr(exc, 'user_message', None) or exc}") from exc

    def _metadata(self, donation, recurring=None):
        meta = {"donation_reference": donation.reference, "appeal_code": donation.appeal_code or ""}
        if recurring:
            meta["recurring_reference"] = recurring.reference
        return meta

    def start_one_time(self, donation, return_url, cancel_url):
        session = self._wrap(
            self.client.v1.checkout.sessions.create,
            {
                "mode": "payment",
                "customer_email": donation.email,
                "client_reference_id": donation.reference,
                "line_items": [
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": to_cents(donation.amount),
                            "product_data": {"name": "Donation"},
                        },
                    }
                ],
                "metadata": self._metadata(donation),
                "payment_intent_data": {"metadata": self._metadata(donation)},
                "success_url": return_url,
                "cancel_url": cancel_url,
                "submit_type": "donate",
            },
        )
        return session.url

    def start_recurring(self, donation, recurring, return_url, cancel_url):
        session = self._wrap(
            self.client.v1.checkout.sessions.create,
            {
                "mode": "subscription",
                "customer_email": donation.email,
                "client_reference_id": donation.reference,
                "line_items": [
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": to_cents(donation.amount),
                            "recurring": {"interval": "month"},
                            "product_data": {"name": "Monthly gift"},
                        },
                    }
                ],
                "metadata": self._metadata(donation, recurring),
                "subscription_data": {"metadata": self._metadata(donation, recurring)},
                "success_url": return_url,
                "cancel_url": cancel_url,
            },
        )
        return session.url

    def cancel_recurring(self, recurring):
        self._wrap(self.client.v1.subscriptions.cancel, recurring.provider_subscription_id)

    def pause_recurring(self, recurring):
        self._wrap(
            self.client.v1.subscriptions.update,
            recurring.provider_subscription_id,
            {"pause_collection": {"behavior": "void"}},
        )

    def resume_recurring(self, recurring):
        self._wrap(self.client.v1.subscriptions.update, recurring.provider_subscription_id, {"pause_collection": ""})

    def change_recurring(self, recurring, amount=None, day_of_month=None):
        sub = self._wrap(self.client.v1.subscriptions.retrieve, recurring.provider_subscription_id)
        params = {"proration_behavior": "none"}
        if amount is not None:
            price = self._wrap(
                self.client.v1.prices.create,
                {
                    "currency": "usd",
                    "unit_amount": to_cents(amount),
                    "recurring": {"interval": "month"},
                    "product_data": {"name": "Monthly gift"},
                },
            )
            params["items"] = [{"id": sub["items"]["data"][0]["id"], "price": price.id}]
            recurring.amount = amount
        if day_of_month:
            from .paystack import _next_date_for_day

            next_date = _next_date_for_day(day_of_month)
            anchor = timezone.make_aware(datetime.combine(next_date, time(9, 0)))
            params["trial_end"] = int(anchor.timestamp())
            recurring.day_of_month = day_of_month
            recurring.next_charge_date = next_date
        self._wrap(self.client.v1.subscriptions.update, recurring.provider_subscription_id, params)

    def manage_card_url(self, recurring, return_url):
        if not recurring.provider_customer_id:
            raise PaymentError("No Stripe customer on this gift yet")
        session = self._wrap(
            self.client.v1.billing_portal.sessions.create,
            {"customer": recurring.provider_customer_id, "return_url": return_url},
        )
        return session.url

    def refund(self, donation):
        if not donation.provider_reference.startswith("pi_"):
            raise PaymentError("No Stripe payment to refund")
        self._wrap(self.client.v1.refunds.create, {"payment_intent": donation.provider_reference})

    def parse_webhook(self, request):
        try:
            event = stripe.Webhook.construct_event(
                request.body, request.headers.get("Stripe-Signature"), settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise PaymentError(f"Invalid Stripe webhook: {exc}") from exc
        return event.id, event.type, json.loads(request.body)
