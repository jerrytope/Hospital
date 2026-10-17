import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.fundraising.models import Fundraiser, FundraiserReport
from apps.giving import services
from apps.giving.emails import send_templated
from apps.giving.models import BankTransferNotice, Donation, ECard, RecurringGift, money
from apps.giving.tasks import send_receipt
from apps.newsletter.models import Subscriber
from apps.payments.handlers import process_event
from apps.payments.models import WebhookEvent
from apps.payments.providers import PaymentError, get_provider


def _require(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied


def _start_of(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _totals(qs):
    return {row["currency"]: row["total"] for row in qs.values("currency").annotate(total=Sum("amount"))}


def _fmt_totals(totals):
    return ", ".join(money(v, k) for k, v in sorted(totals.items())) or "—"


def overview_stats(user):
    """Figures for the admin home panel and the giving overview."""
    today = timezone.localdate()
    paid = Donation.objects.filter(status="succeeded")
    stats = {
        "today": _fmt_totals(_totals(paid.filter(paid_at__gte=_start_of(today)))),
        "week": _fmt_totals(_totals(paid.filter(paid_at__gte=_start_of(today - timedelta(days=6))))),
        "month": _fmt_totals(_totals(paid.filter(paid_at__gte=_start_of(today - timedelta(days=29))))),
        "gifts_30d": paid.filter(paid_at__gte=_start_of(today - timedelta(days=29))).count(),
        "new_monthly_30d": RecurringGift.objects.filter(
            status__in=["active", "paused"], created_at__gte=_start_of(today - timedelta(days=29))
        ).count(),
        "active_monthly": RecurringGift.objects.filter(status="active").count(),
        "pending_bank": BankTransferNotice.objects.filter(status="pending").count(),
        "pending_fundraisers": Fundraiser.objects.filter(status="pending").count(),
        "edited_fundraisers": Fundraiser.objects.filter(edited_since_review=True, status="live").count(),
        "open_reports": FundraiserReport.objects.filter(resolved=False).count(),
        "failed_ecards": ECard.objects.filter(status="failed").count(),
        "failed_webhooks": WebhookEvent.objects.exclude(error="").count(),
        "past_due": RecurringGift.objects.filter(status="past_due").count(),
        "new_subscribers_30d": Subscriber.objects.filter(
            status="subscribed", created_at__gte=_start_of(today - timedelta(days=29))
        ).count(),
    }
    since = _start_of(today - timedelta(days=29))
    stats["top_appeals"] = (
        paid.filter(paid_at__gte=since)
        .values("appeal_code", "currency")
        .annotate(total=Sum("amount"), gifts=Count("id"))
        .order_by("-gifts")[:6]
    )
    for row in stats["top_appeals"]:
        row["display"] = money(row["total"], row["currency"])
    return stats


def giving_overview(request):
    _require(request, "giving.view_donation")
    stats = overview_stats(request.user)
    emergencies = (
        Donation.objects.filter(status="succeeded", emergency__isnull=False)
        .values("emergency__title", "currency")
        .annotate(total=Sum("amount"), gifts=Count("id"))
        .order_by("emergency__title")
    )
    for row in emergencies:
        row["display"] = money(row["total"], row["currency"])
    recent = Donation.objects.filter(status="succeeded").order_by("-paid_at")[:10]
    return render(
        request,
        "dashboard/overview.html",
        {"stats": stats, "emergencies": emergencies, "recent": recent, "fake_mode": settings.PAYMENTS_FAKE_MODE},
    )


# --- Appeals report ------------------------------------------------------------------------


def appeals_report(request):
    _require(request, "giving.view_donation")
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get("start", ""))
    except ValueError:
        start = today - timedelta(days=29)
    try:
        end = date.fromisoformat(request.GET.get("end", ""))
    except ValueError:
        end = today
    qs = Donation.objects.filter(
        status="succeeded", paid_at__gte=_start_of(start), paid_at__lt=_start_of(end + timedelta(days=1))
    )
    by_appeal = list(
        qs.values("appeal_code", "appeal__name", "currency").annotate(total=Sum("amount"), gifts=Count("id")).order_by("-total")
    )
    by_emergency = list(
        qs.filter(emergency__isnull=False)
        .values("emergency__title", "currency")
        .annotate(total=Sum("amount"), gifts=Count("id"))
        .order_by("-total")
    )
    by_method = list(qs.values("provider", "currency").annotate(total=Sum("amount"), gifts=Count("id")).order_by("provider"))
    for rows in (by_appeal, by_emergency, by_method):
        for row in rows:
            row["display"] = money(row["total"], row["currency"])
    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="appeals-{start}-to-{end}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Appeal code", "Appeal name", "Currency", "Gifts", "Total"])
        for row in by_appeal:
            writer.writerow([row["appeal_code"] or "(none)", row["appeal__name"] or "", row["currency"], row["gifts"], row["total"]])
        return response
    return render(
        request,
        "dashboard/appeals_report.html",
        {"start": start, "end": end, "by_appeal": by_appeal, "by_emergency": by_emergency, "by_method": by_method,
         "totals": _fmt_totals(_totals(qs)), "count": qs.count()},
    )


# --- Bank transfer queue ---------------------------------------------------------------------


def bank_transfers(request):
    _require(request, "giving.view_banktransfernotice")
    status = request.GET.get("status", "pending")
    notices = BankTransferNotice.objects.select_related("bank_account", "emergency", "reviewed_by", "donation")
    if status in ("pending", "confirmed", "rejected"):
        notices = notices.filter(status=status)
    counts = {row["status"]: row["n"] for row in BankTransferNotice.objects.values("status").annotate(n=Count("id"))}
    return render(request, "dashboard/bank_transfers.html", {"notices": notices[:200], "status": status, "counts": counts})


@require_POST
def bank_transfer_action(request, pk):
    _require(request, "giving.change_banktransfernotice")
    notice = get_object_or_404(BankTransferNotice, pk=pk)
    action = request.POST.get("action")
    if notice.status != "pending":
        messages.error(request, f"{notice.reference} has already been {notice.get_status_display().lower()}.")
    elif action == "confirm":
        amount = None
        raw = (request.POST.get("amount") or "").replace(",", "").strip()
        if raw:
            try:
                amount = Decimal(raw)
            except InvalidOperation:
                messages.error(request, "Enter the amount that actually arrived, e.g. 25000")
                return redirect(reverse("dashboard_bank_transfers"))
        donation = services.confirm_bank_notice(notice, request.user, amount=amount)
        messages.success(request, f"Confirmed {notice.reference}. Donation {donation.reference} recorded and receipt sent.")
    elif action == "reject":
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Give a short reason; it is emailed to the donor.")
        else:
            services.reject_bank_notice(notice, request.user, reason)
            messages.success(request, f"Rejected {notice.reference}. The donor has been emailed.")
    return redirect(reverse("dashboard_bank_transfers") + "?status=pending")


# --- Fundraiser moderation -------------------------------------------------------------------


def fundraisers(request):
    _require(request, "fundraising.change_fundraiser")
    status = request.GET.get("status", "pending")
    qs = Fundraiser.objects.select_related("owner", "emergency").annotate(
        open_reports=Count("reports", filter=Q(reports__resolved=False))
    )
    if status == "edited":
        qs = qs.filter(edited_since_review=True, status="live")
    elif status == "reported":
        qs = qs.filter(open_reports__gt=0)
    elif status != "all":
        qs = qs.filter(status=status)
    counts = {row["status"]: row["n"] for row in Fundraiser.objects.values("status").annotate(n=Count("id"))}
    counts["edited"] = Fundraiser.objects.filter(edited_since_review=True, status="live").count()
    counts["reported"] = Fundraiser.objects.filter(reports__resolved=False).distinct().count()
    return render(request, "dashboard/fundraisers.html", {"fundraisers": qs[:200], "status": status, "counts": counts})


@require_POST
def fundraiser_action(request, pk):
    _require(request, "fundraising.change_fundraiser")
    f = get_object_or_404(Fundraiser, pk=pk)
    action = request.POST.get("action")
    note = (request.POST.get("note") or "").strip()
    notify = False
    if action == "approve":
        f.status = "live"
        f.ever_approved = True
        f.edited_since_review = False
        f.staff_note = ""
        notify = True
    elif action == "changes":
        if not note:
            messages.error(request, "Write what needs changing; the fundraiser will see it.")
            return redirect(request.headers.get("Referer") or reverse("dashboard_fundraisers"))
        f.status = "changes"
        f.staff_note = note
        notify = True
    elif action == "hide":
        f.status = "hidden"
        f.staff_note = note
        notify = True
    elif action == "restore" and f.status == "hidden":
        f.status = "live" if f.ever_approved else "pending"
    elif action == "reviewed":
        f.edited_since_review = False
    elif action == "feature":
        f.featured = not f.featured
    elif action == "resolve_reports":
        f.reports.update(resolved=True)
    f.save()
    if notify:
        send_templated(f.owner.email, f"Your fundraiser: {f.title}", "fundraiser_status", {"fundraiser": f})
    messages.success(request, f"“{f.title}” updated.")
    return redirect(request.headers.get("Referer") or reverse("dashboard_fundraisers"))


# --- Donation / monthly / webhook actions ----------------------------------------------------


@require_POST
def donation_action(request, pk):
    _require(request, "giving.change_donation")
    donation = get_object_or_404(Donation, pk=pk)
    action = request.POST.get("action")
    if action == "resend_receipt" and donation.status == "succeeded":
        Donation.objects.filter(pk=pk).update(receipt_sent_at=None)
        send_receipt.delay(donation.pk)
        messages.success(request, f"Receipt for {donation.reference} is being re-sent to {donation.email}.")
    elif action == "refund" and donation.status == "succeeded":
        try:
            if donation.provider not in ("bank",):
                get_provider(donation.provider).refund(donation)
            services.donation_refunded(donation, note=f"Refunded by {request.user} on {timezone.localdate()}")
            messages.success(request, f"{donation.reference} marked as refunded.")
        except PaymentError as exc:
            messages.error(request, f"Refund failed: {exc}")
    return redirect(request.headers.get("Referer") or "/")


@require_POST
def recurring_action(request, pk):
    _require(request, "giving.change_recurringgift")
    gift = get_object_or_404(RecurringGift, pk=pk)
    action = request.POST.get("action")
    if action == "cancel" and gift.status != "cancelled":
        try:
            get_provider(gift.provider).cancel_recurring(gift)
        except PaymentError as exc:
            messages.error(request, f"The provider refused: {exc}. Marked cancelled here; check the provider dashboard.")
        services.mark_recurring_cancelled(gift)
        messages.success(request, f"{gift.reference} cancelled.")
    elif action == "simulate_renewal" and settings.PAYMENTS_FAKE_MODE:
        services.record_renewal(gift, gift.amount, provider_reference=f"fake_renewal_{timezone.now().timestamp()}")
        messages.success(request, "Test renewal recorded.")
    return redirect(request.headers.get("Referer") or "/")


@require_POST
def webhook_retry(request, pk):
    _require(request, "payments.change_webhookevent")
    event = get_object_or_404(WebhookEvent, pk=pk)
    process_event(event)
    if event.error:
        messages.error(request, f"Still failing: {event.error}")
    else:
        messages.success(request, "Event processed.")
    return redirect(request.headers.get("Referer") or "/")
