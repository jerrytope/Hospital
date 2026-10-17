from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import Fundraiser, FundraiserUpdate

MAX_IMAGE_BYTES = 6 * 1024 * 1024


def clean_uploaded_image(f):
    """Size-limit, re-encode and strip EXIF (including GPS) from supporter photos."""
    if not f:
        return f
    if f.size > MAX_IMAGE_BYTES:
        raise forms.ValidationError("Photo is too large (6 MB maximum)")
    from io import BytesIO

    from django.core.files.uploadedfile import InMemoryUploadedFile
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(f)
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError("Upload a JPG, PNG or WEBP photo")
    img = img.convert("RGB")
    img.thumbnail((1800, 1800))
    out = BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)  # re-encoding drops all metadata
    out.seek(0)
    name = (f.name.rsplit(".", 1)[0] or "photo")[:60] + ".jpg"
    return InMemoryUploadedFile(out, "photo", name, "image/jpeg", out.getbuffer().nbytes, None)


class FundraiserForm(forms.ModelForm):
    class Meta:
        model = Fundraiser
        fields = ["title", "story", "photo", "goal", "currency", "end_date", "emergency"]
        widgets = {
            "story": forms.Textarea(attrs={"rows": 8}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.emergencies.models import EmergencyPage

        self.fields["emergency"].queryset = EmergencyPage.objects.live().filter(status__in=["active", "ongoing"])
        self.fields["emergency"].required = False
        self.fields["emergency"].empty_label = "General fund (where it's needed most)"
        if self.instance.pk and self.instance.donations.filter(status="succeeded").exists():
            self.fields["currency"].disabled = True

    def clean_photo(self):
        f = self.cleaned_data.get("photo")
        if f and hasattr(f, "content_type"):
            return clean_uploaded_image(f)
        return f

    def clean_goal(self):
        goal = self.cleaned_data["goal"]
        if goal < Decimal("1"):
            raise forms.ValidationError("Set a goal above zero")
        return goal

    def clean_end_date(self):
        d = self.cleaned_data.get("end_date")
        if d and d < timezone.localdate():
            raise forms.ValidationError("The end date cannot be in the past")
        return d


class FundraiserUpdateForm(forms.ModelForm):
    class Meta:
        model = FundraiserUpdate
        fields = ["text", "photo"]
        widgets = {"text": forms.Textarea(attrs={"rows": 4})}

    def clean_photo(self):
        f = self.cleaned_data.get("photo")
        if f and hasattr(f, "content_type"):
            return clean_uploaded_image(f)
        return f


class ReportForm(forms.Form):
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 4}))
    reporter_email = forms.EmailField(required=False)
    website = forms.CharField(required=False)
