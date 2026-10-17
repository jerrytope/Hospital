"""Paystack (NGN): one-time charges, monthly subscriptions via plans, refunds, webhooks."""
import hashlib
import hmac
import json
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

from .base import PaymentError, Provider

API = "https://api.paystack.co"


def to_kobo(amount):
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


class PaystackProvider(Provider):
    name = "paystack"

    def __init__(self):
        self.secret = settings.PAYSTACK_SECRET_KEY
        if not self.secret:
            raise PaymentError("Paystack is not configured (PAYSTACK_SECRET_KEY is empty)")

    # --- HTTP helper --------------------------------------------------------
    def _call(self, method, path, **kwargs):
        try:
            resp = requests.request(
                method,
                API + path,
                headers={"Authorization": f"Bearer {self.secret}", "Content-Type": "application/json"},
                timeout=20,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise PaymentError(f"Could not reach Paystack: {exc}") from exc
        try:
            data = resp.json()
        except ValueError:
            raise PaymentError(f"Paystack returned an invalid response ({resp.status_code})")
        if resp.status_code >= 400 or not data.get("status"):
            raise PaymentError(f"Paystack error: {data.get('message', resp.status_code)}")
        return data.get("data") or {}

    # --- Checkout -----------------------------------------------------------
    def _metadata(self, donation):
        return {
            "donation_reference": donation.reference,
            "appeal_code": donation.appeal_code,
            "custom_fields": [
                {"display_name": "Appeal", "variable_name": "appeal", "value": donation.appeal_code or "-"}
            ],
        }

    def start_one_time(self, donation, return_url, cancel_url):
        data = self._call(
            "POST",
            "/transaction/initialize",
            json={
                "email": donation.email,
                "amount": to_kobo(donation.amount),
                "currency": "NGN",
                "reference": donation.reference,
                "callback_url": return_url,
                "metadata": self._metadata(donation),
            },
        )
        return data["authorization_url"]

    def _create_plan(self, recurring):
        data = self._call(
            "POST",
            "/plan",
            json={
                "name": f"Monthly gift {recurring.reference}",
                "interval": "monthly",
                "amount": to_kobo(recurring.amount),
                "currency": "NGN",
            },
        )
        return data["plan_code"]

    def start_recurring(self, donation, recurring, return_url, cancel_url):
        plan = self._create_plan(recurring)
        recurring.provider_plan = plan
        recurring.save(update_fields=["provider_plan"])
        data = self._call(
            "POST",
            "/transaction/initialize",
            json={
                "email": donation.email,
                "amount": to_kobo(donation.amount),
                "currency": "NGN",
                "reference": donation.reference,
                "callback_url": return_url,
                "plan": plan,
                "metadata": {**self._metadata(donation), "recurring_reference": recurring.reference},
            },
        )
        return data["authorization_url"]

    # --- Subscription management -------------------------------------------
    def _disable(self, recurring):
        if recurring.provider_subscription_id and recurring.provider_token:
            self._call(
                "POST",
                "/subscription/disable",
                json={"code": recurring.provider_subscription_id, "token": recurring.provider_token},
            )

    def _create_subscription(self, recurring, start_date=None):
        if not recurring.provider_authorization or not recurring.provider_customer_id:
            raise PaymentError("This monthly gift has no saved card yet. Please set it up again.")
        payload = {
            "customer": recurring.provider_customer_id,
            "plan": recurring.provider_plan,
            "authorization": recurring.provider_authorization,
        }
        if start_date:
            payload["start_date"] = start_date.isoformat()
        data = self._call("POST", "/subscription", json=payload)
        recurring.provider_subscription_id = data.get("subscription_code", "")
        recurring.provider_token = data.get("email_token", "")
        if data.get("next_payment_date"):
            recurring.next_charge_date = data["next_payment_date"][:10]

    def cancel_recurring(self, recurring):
        self._disable(recurring)

    def pause_recurring(self, recurring):
        self._disable(recurring)

    def resume_recurring(self, recurring):
        self._create_subscription(recurring)

    def change_recurring(self, recurring, amount=None, day_of_month=None):
        # Paystack plans have a fixed amount, so a change means a new plan and subscription.
        self._disable(recurring)
        if amount is not None:
            recurring.amount = amount
            recurring.provider_plan = self._create_plan(recurring)
        start = None
        if day_of_month:
            start = _next_date_for_day(day_of_month)
            recurring.day_of_month = day_of_month
        self._create_subscription(recurring, start_date=start)

    def manage_card_url(self, recurring, return_url):
        if not recurring.provider_subscription_id:
            raise PaymentError("No active subscription to manage")
        data = self._call("GET", f"/subscription/{recurring.provider_subscription_id}/manage/link")
        return data["link"]

    def refund(self, donation):
        self._call("POST", "/refund", json={"transaction": donation.provider_reference or donation.reference})

    def verify_return(self, donation):
        data = self._call("GET", f"/transaction/verify/{donation.reference}")
        return data if data.get("status") == "success" else None

    # --- Webhooks -------------------------------------------------------------
    def parse_webhook(self, request):
        signature = request.headers.get("X-Paystack-Signature", "")
        expected = hmac.new(self.secret.encode(), request.body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PaymentError("Invalid Paystack signature")
        payload = json.loads(request.body)
        event = payload.get("event", "")
        data = payload.get("data") or {}
        event_id = f"{event}:{data.get('id') or data.get('subscription_code') or data.get('reference')}"
        return event_id, event, payload


def _next_date_for_day(day):
    import calendar
    from datetime import date

    today = timezone.localdate()
    year, month = today.year, today.month
    if today.day >= day:
        month += 1
        if month > 12:
            month, year = 1, year + 1
    day = min(day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
