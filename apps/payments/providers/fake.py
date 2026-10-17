"""Offline test provider for local development (PAYMENTS_FAKE_MODE=true).

Checkout sends the donor to /payments/fake/<reference>/, where they can approve or
decline. Approving builds a provider-style event and passes it through the same
handler code as real webhooks, so the whole donation pipeline is exercised offline.
"""
import json
import secrets

from django.urls import reverse

from .base import PaymentError, Provider


class FakeProvider(Provider):
    name = "fake"

    def start_one_time(self, donation, return_url, cancel_url):
        return reverse("payments:fake_checkout", args=[donation.reference])

    def start_recurring(self, donation, recurring, return_url, cancel_url):
        return reverse("payments:fake_checkout", args=[donation.reference])

    def cancel_recurring(self, recurring):
        return None

    def pause_recurring(self, recurring):
        return None

    def resume_recurring(self, recurring):
        return None

    def change_recurring(self, recurring, amount=None, day_of_month=None):
        if amount is not None:
            recurring.amount = amount
        if day_of_month:
            from .paystack import _next_date_for_day

            recurring.day_of_month = day_of_month
            recurring.next_charge_date = _next_date_for_day(day_of_month)

    def manage_card_url(self, recurring, return_url):
        return return_url + "?card=updated-in-test-mode"

    def refund(self, donation):
        return None

    def parse_webhook(self, request):
        try:
            payload = json.loads(request.body)
        except ValueError as exc:
            raise PaymentError("Invalid JSON") from exc
        return payload.get("id") or secrets.token_hex(8), payload.get("type", ""), payload
