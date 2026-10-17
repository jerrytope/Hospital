import logging
import secrets

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.giving.models import Donation

from .handlers import record_and_handle
from .providers import PaymentError, get_provider

log = logging.getLogger(__name__)


def _webhook(request, provider_name):
    try:
        provider = get_provider(provider_name)
        event_id, event_type, payload = provider.parse_webhook(request)
    except PaymentError as exc:
        log.warning("Rejected %s webhook: %s", provider_name, exc)
        return HttpResponseBadRequest("invalid")
    record_and_handle(provider_name, event_id, event_type, payload)
    # Always 200 once verified: processing errors are logged and retried from the admin.
    return HttpResponse("ok")


@csrf_exempt
@require_POST
def paystack_webhook(request):
    return _webhook(request, "paystack")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    return _webhook(request, "stripe")


def fake_checkout(request, reference):
    """Offline payment page used only when PAYMENTS_FAKE_MODE is on."""
    if not settings.PAYMENTS_FAKE_MODE:
        raise Http404
    donation = get_object_or_404(Donation, reference=reference)
    if request.method == "POST":
        outcome = "payment.succeeded" if request.POST.get("outcome") == "pay" else "payment.failed"
        record_and_handle(
            "fake", f"evt_{secrets.token_hex(6)}", outcome, {"type": outcome, "reference": donation.reference}
        )
        return redirect(reverse("giving:return", args=[donation.reference]))
    return render(request, "payments/fake_checkout.html", {"donation": donation})


@require_POST
def fake_renewal(request, reference):
    """Simulate next month's charge on a test-mode monthly gift (staff only)."""
    if not settings.PAYMENTS_FAKE_MODE or not request.user.is_staff:
        raise Http404
    event_id = f"evt_{secrets.token_hex(6)}"
    record_and_handle("fake", event_id, "subscription.renewed",
                      {"id": event_id, "type": "subscription.renewed", "recurring_reference": reference})
    return redirect(request.headers.get("Referer") or "/")
