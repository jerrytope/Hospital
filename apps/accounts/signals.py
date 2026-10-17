from allauth.account.signals import email_confirmed, user_signed_up
from django.dispatch import receiver

from .models import SupporterProfile


@receiver(email_confirmed)
def attach_guest_gifts(request, email_address, **kwargs):
    """Once a supporter proves they own an email, show their earlier guest gifts."""
    from apps.giving.services import claim_gifts_for_user

    if email_address.email.lower() == email_address.user.email.lower():
        claim_gifts_for_user(email_address.user)


@receiver(user_signed_up)
def create_profile(request, user, **kwargs):
    SupporterProfile.objects.get_or_create(user=user)
