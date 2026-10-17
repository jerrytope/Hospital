from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class AdminTwoFactorMiddleware:
    """Require a verified 2FA device for every admin page once a staff user is logged in.

    Staff without a device are sent to set one up; staff with a device but an unverified
    session are sent to enter their code. Login, logout and password-reset pages stay open.
    """

    OPEN_SUFFIXES = ("login/", "logout/", "password_reset/", "jsi18n/", "2fa/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "ADMIN_REQUIRE_2FA", True) and self._needs_check(request):
            from django_otp import user_has_device

            user = request.user
            if not user.is_verified():
                if user_has_device(user):
                    return redirect(f"{reverse('two_factor_verify')}?next={request.get_full_path()}")
                return redirect(f"{reverse('two_factor_setup')}?next={request.get_full_path()}")
        return self.get_response(request)

    def _needs_check(self, request):
        admin_prefix = f"/{settings.ADMIN_PATH}/"
        path = request.path
        if not path.startswith(admin_prefix):
            return False
        if any(path.startswith(admin_prefix + s) for s in self.OPEN_SUFFIXES):
            return False
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)
