from celery import shared_task
from django.utils import timezone


@shared_task
def daily_housekeeping():
    """End fundraisers past their end date. Tenders and jobs close automatically by deadline."""
    from apps.fundraising.models import Fundraiser

    ended = Fundraiser.objects.filter(status="live", end_date__lt=timezone.localdate()).update(status="ended")
    return {"fundraisers_ended": ended}
