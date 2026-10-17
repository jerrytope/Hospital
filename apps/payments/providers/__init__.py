"""Payment provider registry. The donation currency picks the provider (NGN → Paystack, USD → Stripe).

In local development PAYMENTS_FAKE_MODE replaces both with an offline test provider that
drives the same webhook-handling code paths.
"""
from django.conf import settings

from .base import PaymentError, Provider  # noqa: F401


def get_provider(name):
    if name == "paystack":
        from .paystack import PaystackProvider

        return PaystackProvider()
    if name == "stripe":
        from .stripe_provider import StripeProvider

        return StripeProvider()
    if name == "fake":
        from .fake import FakeProvider

        return FakeProvider()
    raise PaymentError(f"Unknown payment provider {name!r}")


def provider_for_currency(currency):
    if settings.PAYMENTS_FAKE_MODE:
        return get_provider("fake")
    return get_provider("paystack" if currency == "NGN" else "stripe")
