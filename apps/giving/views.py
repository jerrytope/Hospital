import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.emergencies.models import EmergencyPage
from apps.payments.providers import PaymentError, provider_for_currency

from . import services
from .forms import BankTransferNoticeForm, DonationForm, GiftCheckoutForm
from .models import (
    BankAccount,
    BankTransferNotice,
    Donation,
    DonationSettings,
    ECard,
    GiftItem,
    GiftOrder,
    GiftOrderLine,
    money,
)
from .tasks import send_bank_notice_received

log = logging.getLogger(__name__)


def _context_from_request(request):
    """Read appeal / emergency / fundraiser / frequency / currency from the query string."""
    from apps.fundraising.models import Fundraiser

    ds = DonationSettings.load(request_or_site=request)
    appeal = (request.GET.get("appeal") or request.POST.get("appeal_code") or "").strip().upper()[:40]
    emergency = None
    em_id = request.GET.get("emergency") or request.POST.get("emergency")
    if em_id and str(em_id).isdigit():
        emergency = EmergencyPage.objects.live().filter(pk=int(em_id)).first()
    fundraiser = None
    fr_slug = request.GET.get("fundraiser") or request.POST.get("fundraiser")
    if fr_slug:
        fundraiser = Fundraiser.objects.filter(slug=fr_slug, status="live").first()
    if emergency and not appeal and emergency.appeal_code:
        appeal = emergency.appeal_code.upper()

    card_currencies = [c for c, on in (("NGN", ds.enable_paystack), ("USD", ds.enable_stripe)) if on]
    bank_qs = BankAccount.objects.filter(active=True, show_on_donate=True)
    if emergency and bank_qs.filter(emergency=emergency).exists():
        bank_qs = bank_qs.filter(emergency=emergency)
    else:
        bank_qs = bank_qs.filter(emergency__isnull=True)
    bank_accounts = list(bank_qs) if ds.enable_bank_transfer else []
    bank_currencies = sorted({a.currency for a in bank_accounts})

    currencies = [c for c in ("NGN", "USD") if c in card_currencies or c in bank_currencies] or ["NGN"]
    currency = request.GET.get("currency", "").upper()
    if fundraiser:
        currency = fundraiser.currency
    if currency not in currencies:
        currency = ds.default_currency if ds.default_currency in currencies else currencies[0]
    frequency = "monthly" if request.GET.get("frequency") == "monthly" and ds.enable_monthly and not fundraiser else "one_time"
    presets = {c: [_plain(p) for p in ds.presets(c)] for c in ("NGN", "USD")}
    default_amount = presets[currency][1] if len(presets[currency]) > 1 else (presets[currency] or [""])[0]
    requested = (request.GET.get("amount") or "").replace(",", "")
    if requested.replace(".", "", 1).isdigit():
        default_amount = requested

    return {
        "ds": ds,
        "appeal": appeal,
        "emergency": emergency,
        "fundraiser": fundraiser,
        "currencies": currencies,
        "card_currencies": card_currencies,
        "bank_currencies": bank_currencies,
        "bank_accounts": bank_accounts,
        "currency": currency,
        "frequency": frequency,
        "presets": presets,
        "minimums": {"NGN": str(ds.minimum_ngn), "USD": str(ds.minimum_usd)},
        "default_amount": default_amount,
        "default_method": "card" if currency in card_currencies else "bank",
        "suggested_reference": _suggested_reference(appeal),
        "source_url": request.GET.get("source") or request.headers.get("Referer", "")[:500],
        "today": timezone.localdate(),
    }


def _plain(amount):
    """5000 -> '5000', 12.5 -> '12.50' (never scientific notation)."""
    return str(int(amount)) if amount == amount.to_integral_value() else f"{amount:.2f}"


def _donor_initial(request):
    if request.user.is_authenticated:
        u = request.user
        return {"first_name": u.first_name, "last_name": u.last_name, "email": u.email, "phone": u.phone}
    return {}


def _suggested_reference(appeal):
    import secrets

    return f"GIFT-{(appeal or 'GENERAL')[:12]}-{secrets.token_hex(2).upper()}"


def donate_page(request):
    ctx = _context_from_request(request)
    ctx["form"] = DonationForm(settings_obj=ctx["ds"], initial=_donor_initial(request))
    return render(request, "giving/donate_page.html", ctx)


def donate_modal(request):
    ctx = _context_from_request(request)
    ctx["form"] = DonationForm(settings_obj=ctx["ds"], initial=_donor_initial(request))
    return render(request, "giving/donate_modal.html", ctx)


@require_POST
@ratelimit(key="ip", rate="20/h", method="POST", block=True)
def checkout(request):
    ds = DonationSettings.load(request_or_site=request)
    form = DonationForm(request.POST, settings_obj=ds)
    if not form.is_valid():
        ctx = _context_from_request(request)
        ctx.update({"form": form, "currency": request.POST.get("currency", ctx["currency"]),
                    "frequency": request.POST.get("frequency", ctx["frequency"])})
        template = "giving/partials/donate_form.html" if request.headers.get("HX-Request") else "giving/donate_page.html"
        return render(request, template, ctx, status=400 if not request.headers.get("HX-Request") else 200)

    data = form.cleaned_data
    from apps.fundraising.models import Fundraiser

    emergency = EmergencyPage.objects.filter(pk=data["emergency"]).first() if data.get("emergency") else None
    fundraiser = Fundraiser.objects.filter(slug=data["fundraiser"], status="live").first() if data.get("fundraiser") else None
    provider = provider_for_currency(data["currency"])
    donation = services.create_donation(
        amount=data["amount"],
        currency=data["currency"],
        frequency=data["frequency"],
        provider=provider.name,
        donor={k: data[k] for k in ("first_name", "last_name", "email", "phone")},
        appeal_code=data.get("appeal_code") or "",
        emergency=emergency,
        fundraiser=fundraiser,
        source_url=data.get("source_url") or "",
        user=request.user,
        tribute=form.tribute_data(),
        display_name=data.get("display_name") or "",
        is_anonymous=data.get("is_anonymous") or False,
        public_message=data.get("public_message") or "",
    )
    return_url = settings.SITE_URL + reverse("giving:return", args=[donation.reference])
    cancel_url = settings.SITE_URL + reverse("giving:donate") + (f"?appeal={donation.appeal_code}" if donation.appeal_code else "")
    try:
        if donation.recurring_gift_id:
            url = provider.start_recurring(donation, donation.recurring_gift, return_url, cancel_url)
        else:
            url = provider.start_one_time(donation, return_url, cancel_url)
    except PaymentError as exc:
        log.error("Checkout failed for %s: %s", donation.reference, exc)
        donation.status = "failed"
        donation.admin_notes = str(exc)
        donation.save(update_fields=["status", "admin_notes"])
        ctx = _context_from_request(request)
        ctx["form"] = form
        ctx["checkout_error"] = "We couldn't start the payment just now. Please try again, or give by bank transfer."
        template = "giving/partials/donate_form.html" if request.headers.get("HX-Request") else "giving/donate_page.html"
        return render(request, template, ctx)
    request.session["last_donation"] = donation.reference
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


def donation_return(request, reference):
    donation = get_object_or_404(Donation, reference=reference)
    # Only the browser that started the gift (or its signed-in owner) sees the details.
    if request.session.get("last_donation") != reference and not (
        request.user.is_authenticated and donation.user_id == request.user.pk
    ):
        raise Http404
    # The page polls donation_status until the provider's webhook marks the gift paid.
    ds = DonationSettings.load(request_or_site=request)
    return render(request, "giving/return.html", {"donation": donation, "ds": ds})


def donation_status(request, reference):
    donation = get_object_or_404(Donation, reference=reference)
    if request.session.get("last_donation") != reference:
        raise Http404
    ds = DonationSettings.load(request_or_site=request)
    return render(request, "giving/partials/status.html", {"donation": donation, "ds": ds})


# --- Bank transfers -----------------------------------------------------------------


@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def bank_transfer_notice(request):
    ctx = _context_from_request(request)
    initial = {
        "currency": ctx["currency"],
        "appeal_code": ctx["appeal"],
        "emergency": ctx["emergency"].pk if ctx["emergency"] else "",
        "fundraiser": ctx["fundraiser"].slug if ctx["fundraiser"] else "",
        "transfer_date": timezone.localdate(),
        "bank_reference": request.GET.get("ref", ""),
    }
    if request.user.is_authenticated:
        initial.update({"first_name": request.user.first_name, "last_name": request.user.last_name, "email": request.user.email})
    form = BankTransferNoticeForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        from apps.fundraising.models import Fundraiser

        notice = BankTransferNotice.objects.create(
            first_name=d["first_name"],
            last_name=d["last_name"],
            email=d["email"],
            phone=d.get("phone", ""),
            amount=d["amount"],
            currency=d["currency"],
            bank_account=d.get("bank_account"),
            transfer_date=d["transfer_date"],
            bank_reference=d.get("bank_reference", ""),
            proof=d.get("proof"),
            message=d.get("message", ""),
            appeal_code=(d.get("appeal_code") or "BANK-TRANSFER").upper(),
            emergency=EmergencyPage.objects.filter(pk=d["emergency"]).first() if d.get("emergency") else None,
            fundraiser=Fundraiser.objects.filter(slug=d["fundraiser"]).first() if d.get("fundraiser") else None,
            user=request.user if request.user.is_authenticated else None,
        )
        send_bank_notice_received.delay(notice.pk)
        return render(request, "giving/bank_notice_thanks.html", {"notice": notice})
    ctx["form"] = form
    return render(request, "giving/bank_notice.html", ctx)


# --- Gifts catalog cart -------------------------------------------------------------


def _cart(request):
    cart = request.session.get("gift_cart") or {"currency": "NGN", "items": {}}
    cart.setdefault("items", {})
    cart.setdefault("currency", "NGN")
    return cart


def _cart_lines(cart):
    items = GiftItem.objects.filter(pk__in=[int(k) for k in cart["items"]], active=True)
    lines, total = [], Decimal("0")
    for item in items:
        qty = int(cart["items"].get(str(item.pk), 0))
        if qty <= 0:
            continue
        price = item.price(cart["currency"])
        lines.append({"item": item, "qty": qty, "price": price, "total": price * qty})
        total += price * qty
    return lines, total


def _render_cart(request, cart):
    lines, total = _cart_lines(cart)
    return render(
        request,
        "giving/partials/cart.html",
        {"cart": cart, "lines": lines, "total": total, "display_total": money(total, cart["currency"])},
    )


def cart_view(request):
    return _render_cart(request, _cart(request))


@require_POST
def cart_update(request):
    cart = _cart(request)
    action = request.POST.get("action", "add")
    if request.POST.get("currency") in ("NGN", "USD"):
        cart["currency"] = request.POST["currency"]
    item_id = request.POST.get("item")
    if item_id and GiftItem.objects.filter(pk=item_id, active=True).exists():
        qty = int(cart["items"].get(item_id, 0))
        if action == "add":
            qty += 1
        elif action == "remove":
            qty -= 1
        elif action == "delete":
            qty = 0
        qty = max(0, min(qty, 50))
        if qty:
            cart["items"][item_id] = qty
        else:
            cart["items"].pop(item_id, None)
    request.session["gift_cart"] = cart
    return _render_cart(request, cart)


@ratelimit(key="ip", rate="20/h", method="POST", block=True)
def gift_checkout(request):
    cart = _cart(request)
    lines, total = _cart_lines(cart)
    if not lines:
        messages.info(request, "Your gift basket is empty.")
        return redirect(request.GET.get("next") or "/")
    initial = {"send_ecard": True}
    if request.user.is_authenticated:
        initial.update({"first_name": request.user.first_name, "last_name": request.user.last_name, "email": request.user.email})
    form = GiftCheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        provider = provider_for_currency(cart["currency"])
        donation = services.create_donation(
            amount=total,
            currency=cart["currency"],
            frequency="one_time",
            provider=provider.name,
            donor={"first_name": d["first_name"], "last_name": d["last_name"], "email": d["email"]},
            appeal_code="GIFTS",
            source_url=request.headers.get("Referer", ""),
            user=request.user,
        )
        order = GiftOrder.objects.create(
            first_name=d["first_name"],
            last_name=d["last_name"],
            email=d["email"],
            user=request.user if request.user.is_authenticated else None,
            currency=cart["currency"],
            total=total,
            donation=donation,
        )
        for line in lines:
            GiftOrderLine.objects.create(
                order=order, item=line["item"], title=line["item"].title, quantity=line["qty"], unit_price=line["price"]
            )
        if d.get("send_ecard"):
            send_date = d.get("send_date") or timezone.localdate()
            from datetime import datetime, time

            send_at = timezone.now() if send_date <= timezone.localdate() else timezone.make_aware(datetime.combine(send_date, time(8, 0)))
            ECard.objects.create(
                gift_order=order,
                card_type="gift",
                sender_name=f"{d['first_name']} {d['last_name']}",
                recipient_name=d["recipient_name"],
                recipient_email=d["recipient_email"],
                message=d.get("message", ""),
                design=d.get("design") or "hope",
                send_at=send_at,
            )
        return_url = settings.SITE_URL + reverse("giving:return", args=[donation.reference])
        cancel_url = settings.SITE_URL + reverse("giving:gift_checkout")
        try:
            url = provider.start_one_time(donation, return_url, cancel_url)
        except PaymentError as exc:
            log.error("Gift checkout failed: %s", exc)
            donation.status = "failed"
            donation.save(update_fields=["status"])
            messages.error(request, "We couldn't start the payment. Please try again.")
            return redirect("giving:gift_checkout")
        request.session["last_donation"] = donation.reference
        request.session["gift_cart"] = {"currency": cart["currency"], "items": {}}
        return redirect(url)
    return render(
        request,
        "giving/gift_checkout.html",
        {"form": form, "lines": lines, "total": total, "display_total": money(total, cart["currency"]), "cart": cart,
         "today": timezone.localdate()},
    )
