import csv
import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.mail import mail_admins
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_otp import login as otp_login
from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.fundraising.forms import FundraiserForm, FundraiserUpdateForm
from apps.fundraising.models import Fundraiser
from apps.giving import services
from apps.giving.models import Donation, DonationSettings, ECard, GiftOrder, RecurringGift
from apps.giving.receipts import receipt_pdf, statement_pdf
from apps.newsletter.models import Subscriber
from apps.payments.providers import PaymentError, get_provider

from .forms import ProfileForm, TokenForm, UserDetailsForm
from .models import SupporterProfile


def _safe_next(request, default):
    nxt = request.GET.get("next") or request.POST.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return default


# --- Admin two-factor authentication -------------------------------------------


@login_required(login_url=f"/{settings.ADMIN_PATH}/login/")
def two_factor_setup(request):
    if not request.user.is_staff:
        raise Http404
    if user_has_device(request.user) and request.user.is_verified():
        return redirect(f"/{settings.ADMIN_PATH}/")
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=request.user, name="Authenticator app", confirmed=False)
    form = TokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if device.verify_token(form.cleaned_data["token"].replace(" ", "")):
            device.confirmed = True
            device.save()
            otp_login(request, device)
            messages.success(request, "Two-factor authentication is on. You'll enter a code each time you sign in.")
            return redirect(_safe_next(request, f"/{settings.ADMIN_PATH}/"))
        form.add_error("token", "That code didn't match. Check the time on your phone and try again.")
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(device.config_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO()
    img.save(buf)
    secret = device.bin_key.hex()
    import base64

    b32 = base64.b32encode(device.bin_key).decode().rstrip("=")
    return render(
        request,
        "accounts/2fa_setup.html",
        {"form": form, "qr_svg": buf.getvalue().decode(), "secret": b32, "hex_secret": secret},
    )


@login_required(login_url=f"/{settings.ADMIN_PATH}/login/")
def two_factor_verify(request):
    if not request.user.is_staff:
        raise Http404
    form = TokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        token = form.cleaned_data["token"].replace(" ", "")
        for device in TOTPDevice.objects.filter(user=request.user, confirmed=True):
            if device.verify_token(token):
                otp_login(request, device)
                return redirect(_safe_next(request, f"/{settings.ADMIN_PATH}/"))
        form.add_error("token", "That code didn't match. Try the newest code in your app.")
    return render(request, "accounts/2fa_verify.html", {"form": form})


# --- Supporter account area -------------------------------------------------------


def _donations_for(user):
    return Donation.objects.filter(Q(user=user) | Q(email__iexact=user.email, user__isnull=True)).filter(
        _verified_email_q(user)
    )


def _verified_email_q(user):
    """Guest gifts under the same email only show once that email is verified."""
    from allauth.account.models import EmailAddress

    if EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists():
        return Q()
    return Q(user=user)


def _recurring_for(user):
    return RecurringGift.objects.filter(Q(user=user)).exclude(status="pending")


@login_required
def dashboard(request):
    user = request.user
    donations = _donations_for(user).filter(status="succeeded")
    totals = donations.values("currency").annotate(total=Sum("amount")).order_by("currency")
    return render(
        request,
        "accounts/dashboard.html",
        {
            "section": "dashboard",
            "recent": donations.select_related("emergency")[:5],
            "totals": totals,
            "gift_count": donations.count(),
            "monthly": _recurring_for(user).filter(status__in=["active", "paused", "past_due"]),
            "fundraisers": user.fundraisers.all()[:3],
            "scheduled_cards": ECard.objects.filter(
                Q(donation__user=user) | Q(gift_order__user=user), status="scheduled"
            ).count(),
        },
    )


@login_required
def profile(request):
    profile_obj, _ = SupporterProfile.objects.get_or_create(user=request.user)
    user_form = UserDetailsForm(request.POST or None, instance=request.user, prefix="u")
    profile_form = ProfileForm(request.POST or None, instance=profile_obj, prefix="p")
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        Subscriber.objects.filter(email__iexact=request.user.email).update(
            first_name=request.user.first_name, last_name=request.user.last_name, sync_status="pending"
        )
        messages.success(request, "Your details have been saved.")
        return redirect("account_profile")
    return render(request, "accounts/profile.html", {"section": "profile", "user_form": user_form, "profile_form": profile_form})


@login_required
def donations(request):
    qs = _donations_for(request.user).exclude(status="pending").select_related("emergency", "fundraiser", "receipt")
    years = sorted({d.paid_at.year for d in qs if d.paid_at and d.status == "succeeded"}, reverse=True)
    return render(request, "accounts/donations.html", {"section": "donations", "donations": qs, "years": years})


@login_required
def receipt_download(request, reference):
    donation = get_object_or_404(_donations_for(request.user), reference=reference, status="succeeded")
    pdf, filename = receipt_pdf(donation)
    return FileResponse(io.BytesIO(pdf), as_attachment=True, filename=filename, content_type="application/pdf")


@login_required
def statement_download(request, year):
    qs = _donations_for(request.user).filter(status="succeeded", paid_at__year=year).order_by("paid_at")
    if not qs.exists():
        raise Http404
    pdf, filename = statement_pdf(request.user, year, qs)
    return FileResponse(io.BytesIO(pdf), as_attachment=True, filename=filename, content_type="application/pdf")


# --- Monthly giving -------------------------------------------------------------------


@login_required
def monthly(request):
    gifts = _recurring_for(request.user)
    return render(
        request,
        "accounts/monthly.html",
        {"section": "monthly", "gifts": gifts, "ds": DonationSettings.load(request_or_site=request),
         "fake_mode": settings.PAYMENTS_FAKE_MODE},
    )


@login_required
@require_POST
def monthly_action(request, reference):
    gift = get_object_or_404(_recurring_for(request.user), reference=reference)
    action = request.POST.get("action")
    if gift.status == "cancelled":
        messages.error(request, "This monthly gift has been cancelled and can't be changed. You can start a new one any time.")
        return redirect("account_monthly")
    provider = get_provider(gift.provider)
    try:
        with transaction.atomic():
            if action == "cancel":
                provider.cancel_recurring(gift)
                services.mark_recurring_cancelled(gift)
                messages.success(request, "Your monthly gift has been cancelled. Thank you for all you've given.")
            elif action == "pause" and gift.status == "active":
                provider.pause_recurring(gift)
                gift.status = "paused"
                gift.save(update_fields=["status"])
                messages.success(request, "Your monthly gift is paused. Resume it whenever you're ready.")
            elif action == "resume" and gift.status == "paused":
                provider.resume_recurring(gift)
                gift.status = "active"
                gift.save()
                messages.success(request, "Welcome back! Your monthly gift is active again.")
            elif action == "change":
                ds = DonationSettings.load(request_or_site=request)
                amount = None
                raw_amount = (request.POST.get("amount") or "").replace(",", "").strip()
                if raw_amount:
                    try:
                        amount = Decimal(raw_amount).quantize(Decimal("0.01"))
                    except InvalidOperation:
                        amount = None
                    if amount is None or amount < ds.minimum(gift.currency):
                        messages.error(request, f"Enter an amount of at least {ds.minimum(gift.currency):,.0f} {gift.currency}.")
                        return redirect("account_monthly")
                    if amount == gift.amount:
                        amount = None
                day = request.POST.get("day")
                day = int(day) if day and day.isdigit() and 1 <= int(day) <= 28 else None
                if day == gift.day_of_month:
                    day = None
                if amount is None and day is None:
                    messages.info(request, "Nothing changed.")
                    return redirect("account_monthly")
                provider.change_recurring(gift, amount=amount, day_of_month=day)
                gift.save()
                messages.success(request, "Your monthly gift has been updated.")
            elif action == "card":
                url = provider.manage_card_url(gift, settings.SITE_URL + reverse("account_monthly"))
                return redirect(url)
            else:
                messages.error(request, "That action isn't available for this gift.")
    except PaymentError as exc:
        messages.error(request, f"We couldn't update your gift: {exc}")
    return redirect("account_monthly")


# --- Tributes and e-cards ---------------------------------------------------------------


def _ecards_for(user):
    return ECard.objects.filter(Q(donation__user=user) | Q(gift_order__user=user)).select_related("donation", "gift_order")


@login_required
def ecards(request):
    cards = _ecards_for(request.user).order_by("-send_at")
    return render(request, "accounts/ecards.html", {"section": "ecards", "cards": cards, "today": timezone.localdate()})


@login_required
@require_POST
def ecard_action(request, pk):
    card = get_object_or_404(_ecards_for(request.user), pk=pk)
    action = request.POST.get("action")
    if action == "edit":
        if not card.editable:
            messages.error(request, "This e-card has already been sent, so it can't be edited.")
            return redirect("account_ecards")
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        recipient_email = (request.POST.get("recipient_email") or "").strip()
        try:
            validate_email(recipient_email)
        except ValidationError:
            messages.error(request, "Enter a valid email address for the recipient.")
            return redirect("account_ecards")
        send_date_raw = request.POST.get("send_date") or ""
        try:
            send_date = date.fromisoformat(send_date_raw)
        except ValueError:
            send_date = timezone.localdate()
        if send_date < timezone.localdate():
            messages.error(request, "Choose today or a later date.")
            return redirect("account_ecards")
        from datetime import datetime, time

        card.recipient_name = (request.POST.get("recipient_name") or card.recipient_name)[:160]
        card.recipient_email = recipient_email
        card.message = (request.POST.get("message") or "")[:1000]
        card.send_at = timezone.now() if send_date == timezone.localdate() else timezone.make_aware(datetime.combine(send_date, time(8, 0)))
        card.save()
        messages.success(request, "Your e-card has been updated.")
    elif action == "cancel":
        if card.editable:
            card.status = "cancelled"
            card.save(update_fields=["status"])
            messages.success(request, "The e-card has been cancelled. Your gift still counts in full.")
    elif action == "resend":
        if card.status in ("sent", "failed") and card.is_paid:
            card.status = "scheduled"
            card.send_at = timezone.now()
            card.attempts = 0
            card.save()
            from apps.giving.tasks import send_ecard

            send_ecard.delay(card.pk)
            messages.success(request, "We're sending the e-card again now.")
    return redirect("account_ecards")


@login_required
def gift_orders(request):
    orders = GiftOrder.objects.filter(user=request.user).exclude(status="pending").prefetch_related("lines", "ecards")
    return render(request, "accounts/gift_orders.html", {"section": "gifts", "orders": orders})


# --- Fundraisers ----------------------------------------------------------------------


@login_required
def fundraisers(request):
    return render(request, "accounts/fundraisers.html", {"section": "fundraisers", "fundraisers": request.user.fundraisers.all()})


def _notify_staff_review(fundraiser):
    from apps.giving.emails import send_templated

    ds = DonationSettings.load()
    to = ds.notify_email
    if to:
        url = f"{settings.SITE_URL}/{settings.ADMIN_PATH}/fundraisers/"
        transaction.on_commit(
            lambda: send_templated(to, f"Fundraiser to review: {fundraiser.title}", "staff_fundraiser_review",
                                   {"fundraiser": fundraiser, "admin_url": url})
        )


@login_required
def fundraiser_edit(request, pk=None):
    fundraiser = get_object_or_404(Fundraiser, pk=pk, owner=request.user) if pk else None
    if fundraiser and fundraiser.status == "hidden":
        messages.error(request, "This fundraiser was hidden by our team. Please contact us.")
        return redirect("account_fundraisers")
    form = FundraiserForm(request.POST or None, request.FILES or None, instance=fundraiser)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        submit = request.POST.get("submit") == "1"
        if obj.ever_approved and obj.status in ("live", "ended"):
            obj.edited_since_review = True  # edits go live but are flagged for staff
        elif submit:
            obj.status = "pending"
        obj.save()
        if submit and obj.status == "pending":
            _notify_staff_review(obj)
            messages.success(request, "Thank you! Your fundraiser has been sent for a quick review. We'll email you when it's live.")
        else:
            messages.success(request, "Your fundraiser has been saved.")
        return redirect("account_fundraisers")
    return render(request, "accounts/fundraiser_form.html", {"section": "fundraisers", "form": form, "fundraiser": fundraiser})


@login_required
def fundraiser_manage(request, pk):
    fundraiser = get_object_or_404(Fundraiser, pk=pk, owner=request.user)
    update_form = FundraiserUpdateForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update" and update_form.is_valid():
            upd = update_form.save(commit=False)
            upd.fundraiser = fundraiser
            upd.save()
            messages.success(request, "Your update has been posted.")
            return redirect("account_fundraiser_manage", pk=pk)
        if action == "end" and fundraiser.status == "live":
            fundraiser.status = "ended"
            fundraiser.save(update_fields=["status"])
            messages.success(request, "Your fundraiser has ended. Thank you for raising support!")
            return redirect("account_fundraiser_manage", pk=pk)
        if action == "thank":
            note = (request.POST.get("thank_message") or "").strip()[:1500]
            emails = sorted(set(fundraiser.donations.filter(status="succeeded").values_list("email", flat=True)))
            if note and emails:
                from apps.giving.emails import send_templated

                for email in emails:
                    send_templated(email, f"A thank-you from {request.user.get_full_name() or 'your fundraiser'}",
                                   "fundraiser_thanks", {"fundraiser": fundraiser, "note": note})
                messages.success(request, f"Your thank-you was sent to {len(emails)} donor(s).")
            else:
                messages.error(request, "Write a short message first.")
            return redirect("account_fundraiser_manage", pk=pk)
    donations = fundraiser.donations.filter(status="succeeded").order_by("-paid_at")
    return render(
        request,
        "accounts/fundraiser_manage.html",
        {"section": "fundraisers", "fundraiser": fundraiser, "donations": donations, "update_form": update_form,
         "share_url": settings.SITE_URL + fundraiser.get_absolute_url()},
    )


# --- Email preferences, data export, deletion ------------------------------------------


@login_required
def email_preferences(request):
    sub = Subscriber.objects.filter(email__iexact=request.user.email).first()
    if request.method == "POST":
        wants = request.POST.get("newsletter") == "on"
        if wants:
            sub, _ = Subscriber.objects.update_or_create(
                email=request.user.email.lower(),
                defaults={
                    "first_name": request.user.first_name or "Supporter",
                    "last_name": request.user.last_name or "",
                    "status": "subscribed",
                    "consent_at": timezone.now(),
                    "consent_text": "Opted in from account email preferences",
                    "source_page": "/account/email/",
                    "user": request.user,
                    "sync_status": "pending",
                },
            )
        elif sub:
            sub.status = "unsubscribed"
            sub.sync_status = "pending"
            sub.save(update_fields=["status", "sync_status", "updated_at"])
        if sub:
            from apps.newsletter.tasks import sync_subscriber

            sync_subscriber.delay(sub.pk)
        profile_obj, _ = SupporterProfile.objects.get_or_create(user=request.user)
        profile_obj.email_updates = wants
        profile_obj.save(update_fields=["email_updates"])
        messages.success(request, "Your email preferences have been saved.")
        return redirect("account_email_prefs")
    return render(request, "accounts/email_prefs.html", {"section": "email", "subscribed": bool(sub and sub.status == "subscribed")})


@login_required
def export_data(request):
    user = request.user
    data = {
        "account": {"email": user.email, "first_name": user.first_name, "last_name": user.last_name,
                    "phone": user.phone, "joined": user.date_joined.isoformat()},
        "donations": [
            {"reference": d.reference, "date": (d.paid_at or d.created_at).isoformat(), "amount": str(d.amount),
             "currency": d.currency, "frequency": d.frequency, "status": d.status, "appeal": d.appeal_code}
            for d in _donations_for(user)
        ],
        "monthly_gifts": [
            {"reference": r.reference, "amount": str(r.amount), "currency": r.currency, "status": r.status}
            for r in _recurring_for(user)
        ],
        "fundraisers": [{"title": f.title, "goal": str(f.goal), "status": f.status} for f in user.fundraisers.all()],
    }
    response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="my-data.json"'
    return response


@login_required
def delete_account(request):
    user = request.user
    blockers = []
    if user.fundraisers.filter(status="live").exists():
        blockers.append("End your live fundraisers first.")
    if user.is_staff:
        blockers.append("Staff accounts are removed by the site owner in the admin.")
    if request.method == "POST" and not blockers:
        if request.POST.get("confirm") != "DELETE":
            messages.error(request, "Type DELETE to confirm.")
            return redirect("account_delete")
        for gift in _recurring_for(user).filter(status__in=["active", "paused", "past_due"]):
            try:
                get_provider(gift.provider).cancel_recurring(gift)
            except PaymentError:
                mail_admins("Cancel monthly gift manually", f"Could not cancel {gift.reference} during account deletion.")
            services.mark_recurring_cancelled(gift)
        logout(request)
        services.anonymise_user(user)
        messages.success(request, "Your account has been deleted. Thank you for your support.")
        return redirect("/")
    return render(request, "accounts/delete.html", {"section": "profile", "blockers": blockers})
