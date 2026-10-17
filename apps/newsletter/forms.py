from django import forms


class SubscribeForm(forms.Form):
    first_name = forms.CharField(max_length=120)
    last_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)
    source_page = forms.CharField(max_length=500, required=False)
    website = forms.CharField(required=False)  # honeypot

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam detected")
        return ""
