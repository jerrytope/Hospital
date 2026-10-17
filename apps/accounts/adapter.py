from allauth.account.adapter import DefaultAccountAdapter


class SupporterAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=commit)
        if commit:
            from .models import SupporterProfile

            SupporterProfile.objects.get_or_create(user=user)
        return user
