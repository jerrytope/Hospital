from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Remove a staff member's authenticator so they set up a new one at next sign-in (lost phone)."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, email, **options):
        user = get_user_model().objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError(f"No user with email {email}")
        n = TOTPDevice.objects.filter(user=user).delete()[0] + StaticDevice.objects.filter(user=user).delete()[0]
        self.stdout.write(self.style.SUCCESS(f"Removed {n} device(s) for {user.email}. They will set up 2FA again at next sign-in."))
