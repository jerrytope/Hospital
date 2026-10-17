from django.shortcuts import render
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.core.models import OrganisationSettings
from apps.core.turnstile import turnstile_ok

from .forms import SubscribeForm
from .models import Subscriber
from .tasks import sync_subscriber


@require_POST
@ratelimit(key="ip", rate="15/h", method="POST", block=True)
def subscribe(request):
    form = SubscribeForm(request.POST)
    template_form = "newsletter/form.html"
    if not form.is_valid() or not turnstile_ok(request):
        if form.is_valid():
            form.add_error(None, "Please complete the spam check and try again.")
        if form.errors.get("website"):
            # Honeypot hit: pretend it worked so bots learn nothing.
            return render(request, "newsletter/thanks.html", {"subscriber": None})
        return render(request, template_form, {"nl_form": form, "form_id": "retry"})
    d = form.cleaned_data
    org = OrganisationSettings.load(request_or_site=request)
    subscriber, _ = Subscriber.objects.update_or_create(
        email=d["email"].lower(),
        defaults={
            "first_name": d["first_name"],
            "last_name": d["last_name"],
            "phone": d.get("phone", ""),
            "status": "subscribed",
            "consent_at": timezone.now(),
            "consent_text": strip_tags(org.newsletter_consent_text),
            "source_page": d.get("source_page", "")[:500],
            "sync_status": "pending",
            "user": request.user if request.user.is_authenticated else None,
        },
    )
    sync_subscriber.delay(subscriber.pk)
    if request.headers.get("HX-Request"):
        return render(request, "newsletter/thanks.html", {"subscriber": subscriber})
    return render(request, "newsletter/thanks_page.html", {"subscriber": subscriber})


def unsubscribe(request, token):
    subscriber = Subscriber.from_token(token)
    done = False
    if subscriber and request.method == "POST":
        subscriber.status = "unsubscribed"
        subscriber.sync_status = "pending"
        subscriber.save(update_fields=["status", "sync_status", "updated_at"])
        sync_subscriber.delay(subscriber.pk)
        done = True
    return render(request, "newsletter/unsubscribe.html", {"subscriber": subscriber, "done": done, "token": token})
