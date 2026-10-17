from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django import forms
from django.utils import timezone

from .models import BankAccount, DonationSettings, ECard


class HoneypotMixin:
    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam detected")
        return ""


class DonationForm(HoneypotMixin, forms.Form):
    currency = forms.ChoiceField(choices=[("NGN", "NGN"), ("USD", "USD")])
    frequency = forms.ChoiceField(choices=[("one_time", "One-time"), ("monthly", "Monthly")])
    amount = forms.CharField(max_length=20)
    first_name = forms.CharField(max_length=120)
    last_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)

    appeal_code = forms.CharField(max_length=40, required=False)
    emergency = forms.IntegerField(required=False)
    fundraiser = forms.CharField(max_length=140, required=False)
    source_url = forms.CharField(max_length=500, required=False)

    # Fundraiser display options
    display_name = forms.CharField(max_length=120, required=False)
    is_anonymous = forms.BooleanField(required=False)
    public_message = forms.CharField(max_length=280, required=False)

    # Tribute / e-card
    tribute = forms.BooleanField(required=False)
    card_type = forms.ChoiceField(choices=[("honor", "In honour of"), ("memory", "In memory of")], required=False)
    honoree_name = forms.CharField(max_length=160, required=False)
    recipient_name = forms.CharField(max_length=160, required=False)
    recipient_email = forms.EmailField(required=False)
    message = forms.CharField(max_length=1000, required=False, widget=forms.Textarea)
    send_date = forms.DateField(required=False)
    design = forms.ChoiceField(choices=ECard.DESIGN_CHOICES, required=False)

    website = forms.CharField(required=False)  # honeypot

    def __init__(self, *args, settings_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ds = settings_obj or DonationSettings.load()

    def clean_amount(self):
        raw = (self.cleaned_data.get("amount") or "").replace(",", "").replace("₦", "").replace("$", "").strip()
        try:
            amount = Decimal(raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Enter an amount")
        if amount <= 0:
            raise forms.ValidationError("Enter an amount")
        if amount > Decimal("100000000"):
            raise forms.ValidationError("For very large gifts please contact us directly")
        return amount

    def clean(self):
        data = super().clean()
        currency = data.get("currency")
        amount = data.get("amount")
        if currency and amount is not None:
            minimum = self.ds.minimum(currency)
            if amount < minimum:
                self.add_error("amount", f"The minimum gift is {minimum:,.0f} {currency}")
        if currency == "NGN" and not self.ds.enable_paystack:
            self.add_error("currency", "Card payments in Naira are not available right now")
        if currency == "USD" and not self.ds.enable_stripe:
            self.add_error("currency", "Card payments in US dollars are not available right now")
        if data.get("frequency") == "monthly":
            if not self.ds.enable_monthly:
                self.add_error("frequency", "Monthly giving is not available right now")
            if data.get("fundraiser"):
                self.add_error("frequency", "Gifts to a fundraiser are one-time gifts")
        if data.get("tribute"):
            if data.get("card_type") not in ("honor", "memory"):
                self.add_error("card_type", "Choose honour or memory")
            if not data.get("honoree_name"):
                self.add_error("honoree_name", "Who is this gift for?")
            if data.get("recipient_email") and not data.get("recipient_name"):
                self.add_error("recipient_name", "Who should receive the e-card?")
            send_date = data.get("send_date")
            if send_date and send_date < timezone.localdate():
                self.add_error("send_date", "Choose today or a later date")
        return data

    def tribute_data(self):
        d = self.cleaned_data
        if not d.get("tribute") or not d.get("recipient_email"):
            return None
        send_date = d.get("send_date") or timezone.localdate()
        send_at = timezone.now() if send_date <= timezone.localdate() else timezone.make_aware(datetime.combine(send_date, time(8, 0)))
        return {
            "card_type": d["card_type"],
            "honoree_name": d["honoree_name"],
            "sender_name": f"{d['first_name']} {d['last_name']}".strip(),
            "recipient_name": d["recipient_name"],
            "recipient_email": d["recipient_email"],
            "message": d.get("message", ""),
            "design": d.get("design") or "hope",
            "send_at": send_at,
        }


class BankTransferNoticeForm(HoneypotMixin, forms.Form):
    first_name = forms.CharField(max_length=120)
    last_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1"))
    currency = forms.ChoiceField(choices=BankAccount.BANK_CURRENCIES)
    bank_account = forms.ModelChoiceField(queryset=BankAccount.objects.filter(active=True), required=False)
    transfer_date = forms.DateField()
    bank_reference = forms.CharField(max_length=120, required=False)
    proof = forms.FileField(required=False)
    message = forms.CharField(max_length=1000, required=False, widget=forms.Textarea)
    appeal_code = forms.CharField(max_length=40, required=False)
    emergency = forms.IntegerField(required=False)
    fundraiser = forms.CharField(max_length=140, required=False)
    consent = forms.BooleanField(error_messages={"required": "Please confirm the details are correct"})
    website = forms.CharField(required=False)

    MAX_PROOF_BYTES = 8 * 1024 * 1024
    PROOF_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/heic"}

    def clean_transfer_date(self):
        d = self.cleaned_data["transfer_date"]
        if d > timezone.localdate():
            raise forms.ValidationError("The transfer date cannot be in the future")
        return d

    def clean_proof(self):
        f = self.cleaned_data.get("proof")
        if not f:
            return f
        if f.size > self.MAX_PROOF_BYTES:
            raise forms.ValidationError("The file is too large (8 MB maximum)")
        content_type = getattr(f, "content_type", "")
        if content_type not in self.PROOF_TYPES:
            raise forms.ValidationError("Upload a PDF or a photo (JPG, PNG, WEBP)")
        return f


class GiftCheckoutForm(HoneypotMixin, forms.Form):
    first_name = forms.CharField(max_length=120)
    last_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    send_ecard = forms.BooleanField(required=False, initial=True)
    recipient_name = forms.CharField(max_length=160, required=False)
    recipient_email = forms.EmailField(required=False)
    message = forms.CharField(max_length=1000, required=False, widget=forms.Textarea)
    send_date = forms.DateField(required=False)
    design = forms.ChoiceField(choices=ECard.DESIGN_CHOICES, required=False)
    website = forms.CharField(required=False)

    def clean(self):
        data = super().clean()
        if data.get("send_ecard"):
            if not data.get("recipient_email"):
                self.add_error("recipient_email", "Who should receive the e-card?")
            if not data.get("recipient_name"):
                self.add_error("recipient_name", "Enter the recipient's name")
            if data.get("send_date") and data["send_date"] < timezone.localdate():
                self.add_error("send_date", "Choose today or a later date")
        return data
