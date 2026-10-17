from django import forms
from wagtail.images.forms import BaseImageForm


class CustomImageForm(BaseImageForm):
    """Image library form: alt text is required so every published image is accessible."""

    def clean_alt_text(self):
        value = (self.cleaned_data.get("alt_text") or "").strip()
        if not value:
            raise forms.ValidationError("Describe the image for people using screen readers.")
        return value
