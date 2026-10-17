from django import forms

from .models import SupporterProfile, User


class SupporterSignupForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)

    def signup(self, request, user):
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.save()
        SupporterProfile.objects.get_or_create(user=user)


class UserDetailsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = SupporterProfile
        fields = [
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "postcode",
            "preferred_currency",
            "email_updates",
        ]


class TokenForm(forms.Form):
    token = forms.CharField(
        label="6-digit code",
        max_length=8,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric", "autofocus": True}),
    )
