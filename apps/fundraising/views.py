from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .forms import ReportForm
from .models import Fundraiser, FundraiserReport


def fundraiser_list(request):
    live = Fundraiser.objects.filter(status="live").select_related("owner", "emergency")
    return render(
        request,
        "fundraising/list.html",
        {"featured": live.filter(featured=True)[:3], "fundraisers": live.order_by("-created_at")[:24]},
    )


def fundraiser_detail(request, slug):
    fundraiser = get_object_or_404(Fundraiser.objects.select_related("owner", "emergency"), slug=slug)
    is_owner = request.user.is_authenticated and fundraiser.owner_id == request.user.pk
    if not fundraiser.is_public and not is_owner and not request.user.is_staff:
        raise Http404
    donations = fundraiser.donations.filter(status="succeeded").order_by("-paid_at")[:20]
    return render(
        request,
        "fundraising/detail.html",
        {
            "fundraiser": fundraiser,
            "donations": donations,
            "updates": fundraiser.updates.all()[:10],
            "is_owner": is_owner,
            "report_form": ReportForm(),
        },
    )


@require_POST
@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def report_fundraiser(request, slug):
    fundraiser = get_object_or_404(Fundraiser, slug=slug, status__in=["live", "ended"])
    form = ReportForm(request.POST)
    if form.is_valid() and not form.cleaned_data.get("website"):
        FundraiserReport.objects.create(
            fundraiser=fundraiser,
            reason=form.cleaned_data["reason"],
            reporter_email=form.cleaned_data.get("reporter_email", ""),
        )
        messages.success(request, "Thank you. Our team will review this page.")
    else:
        messages.error(request, "Please tell us what is wrong with this page.")
    return redirect(fundraiser.get_absolute_url())


def start(request):
    if request.user.is_authenticated:
        return redirect("account_fundraiser_create")
    return render(request, "fundraising/start.html")
