import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.models import Orderable
from wagtail.search import index

from apps.core.blocks import RICH_FEATURES
from apps.core.models import BasePage

CURRENCY_CHOICES = [("NGN", "Naira (NGN)"), ("USD", "US Dollar (USD)")]
CURRENCY_SYMBOLS = {"NGN": "₦", "USD": "$", "GBP": "£", "EUR": "€"}
FREQUENCY_CHOICES = [("one_time", "One-time"), ("monthly", "Monthly")]
PROVIDER_CHOICES = [("paystack", "Paystack"), ("stripe", "Stripe"), ("bank", "Bank transfer"), ("fake", "Test (offline)")]


def make_reference(prefix="DN"):
    return f"{prefix}-{secrets.token_hex(5).upper()}"


def make_monthly_reference():
    return make_reference("MG")


def make_order_reference():
    return make_reference("GO")


def money(amount, currency):
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    if amount is None:
        return ""
    amount = Decimal(amount)
    text = f"{amount:,.2f}"
    if text.endswith(".00"):
        text = text[:-3]
    return f"{symbol}{text}"


# --- Settings ----------------------------------------------------------------


@register_setting(icon="pick")
class DonationSettings(BaseGenericSetting):
    default_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="NGN")
    presets_ngn = models.CharField(
        "Suggested amounts (NGN)", max_length=200, default="5000,10000,25000,50000,100000",
        help_text="Comma-separated",
    )
    presets_usd = models.CharField("Suggested amounts (USD)", max_length=200, default="25,50,100,250,500")
    minimum_ngn = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1000"))
    minimum_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("5"))
    enable_paystack = models.BooleanField("Card payments in Naira (Paystack)", default=True)
    enable_stripe = models.BooleanField("Card payments in US dollars (Stripe)", default=True)
    enable_bank_transfer = models.BooleanField("Bank transfer", default=True)
    enable_monthly = models.BooleanField("Allow monthly giving", default=True)
    modal_heading = models.CharField(max_length=120, default="Make a gift that saves lives")
    thank_you_heading = models.CharField(max_length=120, default="Thank you for your generosity")
    thank_you_text = RichTextField(
        features=["bold", "italic", "link"],
        blank=True,
        default="<p>Your gift is already on its way to families who need it. A receipt has been sent to your email.</p>",
    )
    receipt_tax_text = models.TextField(
        default="No goods or services were provided in exchange for this contribution. Please keep this receipt for "
        "your tax records.",
    )
    receipt_signatory = models.CharField(max_length=120, blank=True, default="Finance Team")
    bank_transfer_intro = RichTextField(
        features=["bold", "italic", "link"],
        blank=True,
        default="<p>Transfer your gift to one of the accounts below. Use the reference shown so we can match your "
        "gift, then tell us about it with the form so we can send your receipt.</p>",
    )
    notify_email = models.EmailField(
        blank=True, help_text="Who is emailed about new bank transfer notices and changes to bank details"
    )

    panels = [
        FieldPanel("default_currency"),
        MultiFieldPanel(
            [FieldRowPanel([FieldPanel("presets_ngn"), FieldPanel("minimum_ngn")]),
             FieldRowPanel([FieldPanel("presets_usd"), FieldPanel("minimum_usd")])],
            heading="Amounts",
        ),
        MultiFieldPanel(
            [FieldPanel("enable_paystack"), FieldPanel("enable_stripe"), FieldPanel("enable_bank_transfer"),
             FieldPanel("enable_monthly")],
            heading="Payment methods shown to donors",
        ),
        FieldPanel("modal_heading"),
        FieldPanel("bank_transfer_intro"),
        MultiFieldPanel([FieldPanel("thank_you_heading"), FieldPanel("thank_you_text")], heading="Thank-you page"),
        MultiFieldPanel([FieldPanel("receipt_tax_text"), FieldPanel("receipt_signatory")], heading="Receipts"),
        FieldPanel("notify_email"),
    ]

    class Meta:
        verbose_name = "Donation settings"

    def presets(self, currency):
        raw = self.presets_ngn if currency == "NGN" else self.presets_usd
        out = []
        for part in raw.split(","):
            part = part.strip().replace(" ", "")
            try:
                out.append(Decimal(part))
            except Exception:
                continue
        return out

    def minimum(self, currency):
        return self.minimum_ngn if currency == "NGN" else self.minimum_usd

    def enabled_currencies(self):
        cur = []
        if self.enable_paystack or (self.enable_bank_transfer and BankAccount.objects.filter(active=True, currency="NGN").exists()):
            cur.append("NGN")
        if self.enable_stripe or (self.enable_bank_transfer and BankAccount.objects.filter(active=True, currency="USD").exists()):
            cur.append("USD")
        return cur or ["NGN"]


# --- Appeals -----------------------------------------------------------------


class Appeal(models.Model):
    code = models.CharField(max_length=40, unique=True, help_text="e.g. HOME-HERO, FOOTER, EBOLA-2026")
    name = models.CharField(max_length=160)
    emergency = models.ForeignKey(
        "emergencies.EmergencyPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="appeals"
    )
    description = models.TextField(blank=True)
    goal_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    goal_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="NGN")
    active = models.BooleanField(default=True)
    auto_created = models.BooleanField(default=False, help_text="Created automatically from an unknown code")
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldRowPanel([FieldPanel("code"), FieldPanel("active")]),
        FieldPanel("name"),
        FieldPanel("emergency"),
        FieldPanel("description"),
        FieldRowPanel([FieldPanel("goal_amount"), FieldPanel("goal_currency")]),
    ]

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


# --- Bank accounts -----------------------------------------------------------


class BankAccount(models.Model):
    """Bank account numbers shown to visitors for bank-transfer donations. Managed by the owner."""

    BANK_CURRENCIES = CURRENCY_CHOICES + [("GBP", "Pound sterling (GBP)"), ("EUR", "Euro (EUR)")]

    bank_name = models.CharField(max_length=120)
    account_name = models.CharField(max_length=160)
    account_number = models.CharField(max_length=40)
    currency = models.CharField(max_length=3, choices=BANK_CURRENCIES, default="NGN")
    sort_code = models.CharField("Sort code / routing number", max_length=40, blank=True)
    swift_code = models.CharField("SWIFT / BIC", max_length=40, blank=True)
    iban = models.CharField("IBAN", max_length=60, blank=True)
    branch = models.CharField(max_length=160, blank=True)
    instructions = models.TextField(blank=True, help_text="Extra notes shown under the account, e.g. for international transfers")
    emergency = models.ForeignKey(
        "emergencies.EmergencyPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="bank_accounts",
        help_text="Optional: a dedicated relief account shown on this emergency's page",
    )
    show_on_donate = models.BooleanField("Show in donate pop-up and donate page", default=True)
    show_on_contact = models.BooleanField("Show on the Contact and FAQ pages", default=False)
    show_in_footer = models.BooleanField("Show in the footer", default=False)
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldRowPanel([FieldPanel("bank_name"), FieldPanel("currency")]),
        FieldPanel("account_name"),
        FieldPanel("account_number"),
        FieldRowPanel([FieldPanel("sort_code"), FieldPanel("swift_code")]),
        FieldRowPanel([FieldPanel("iban"), FieldPanel("branch")]),
        FieldPanel("instructions"),
        FieldPanel("emergency"),
        MultiFieldPanel(
            [FieldPanel("show_on_donate"), FieldPanel("show_on_contact"), FieldPanel("show_in_footer")],
            heading="Where it is shown",
        ),
        FieldRowPanel([FieldPanel("active"), FieldPanel("order")]),
    ]

    class Meta:
        ordering = ["order", "currency", "bank_name"]

    def __str__(self):
        return f"{self.bank_name} · {self.account_number} ({self.currency})"


class BankTransferNotice(models.Model):
    STATUS_CHOICES = [("pending", "Pending"), ("confirmed", "Confirmed"), ("rejected", "Rejected")]

    reference = models.CharField(max_length=30, unique=True, default=make_reference)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("1"))])
    currency = models.CharField(max_length=3, choices=BankAccount.BANK_CURRENCIES, default="NGN")
    bank_account = models.ForeignKey(BankAccount, null=True, blank=True, on_delete=models.SET_NULL, related_name="notices")
    transfer_date = models.DateField()
    bank_reference = models.CharField("Reference used on the transfer", max_length=120, blank=True)
    proof = models.FileField(upload_to="transfer-proofs/%Y/%m/", blank=True)
    message = models.TextField(blank=True)
    appeal_code = models.CharField(max_length=40, blank=True)
    emergency = models.ForeignKey("emergencies.EmergencyPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    fundraiser = models.ForeignKey("fundraising.Fundraiser", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    donation = models.OneToOneField("giving.Donation", null=True, blank=True, on_delete=models.SET_NULL, related_name="bank_notice")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {money(self.amount, self.currency)} from {self.email}"

    @property
    def display_amount(self):
        return money(self.amount, self.currency)


# --- Donations -----------------------------------------------------------------


class Donation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
    ]

    reference = models.CharField(max_length=30, unique=True, default=make_reference)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=BankAccount.BANK_CURRENCIES, default="NGN")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="one_time")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES)
    provider_reference = models.CharField(max_length=200, blank=True, db_index=True)

    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="donations")

    appeal_code = models.CharField(max_length=40, blank=True, db_index=True)
    appeal = models.ForeignKey(Appeal, null=True, blank=True, on_delete=models.SET_NULL, related_name="donations")
    emergency = models.ForeignKey("emergencies.EmergencyPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="donations")
    fundraiser = models.ForeignKey("fundraising.Fundraiser", null=True, blank=True, on_delete=models.SET_NULL, related_name="donations")
    recurring_gift = models.ForeignKey("giving.RecurringGift", null=True, blank=True, on_delete=models.SET_NULL, related_name="charges")
    source_url = models.CharField(max_length=500, blank=True)

    display_name = models.CharField(max_length=120, blank=True, help_text="Name shown on a fundraiser page")
    is_anonymous = models.BooleanField(default=False, help_text="Hide the name on fundraiser pages")
    public_message = models.CharField(max_length=280, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    receipt_sent_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "currency", "paid_at"])]

    def __str__(self):
        return f"{self.reference} · {self.display_amount} · {self.get_status_display()}"

    @property
    def display_amount(self):
        return money(self.amount, self.currency)

    @property
    def donor_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def public_name(self):
        if self.is_anonymous:
            return "Anonymous"
        return self.display_name or self.first_name

    def mark_succeeded(self, provider_reference=None, when=None):
        """Idempotent: returns True only on the transition into 'succeeded'."""
        if self.status == "succeeded":
            return False
        self.status = "succeeded"
        self.paid_at = when or timezone.now()
        if provider_reference:
            self.provider_reference = provider_reference
        self.save(update_fields=["status", "paid_at", "provider_reference"])
        return True


class RecurringGift(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending first payment"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("past_due", "Payment failed"),
        ("cancelled", "Cancelled"),
    ]

    reference = models.CharField(max_length=30, unique=True, default=make_monthly_reference)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recurring_gifts")
    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES)
    provider_subscription_id = models.CharField(max_length=200, blank=True, db_index=True)
    provider_customer_id = models.CharField(max_length=200, blank=True)
    provider_token = models.CharField(max_length=200, blank=True, help_text="Paystack email token for managing the card")
    provider_authorization = models.CharField(
        max_length=200, blank=True, help_text="Paystack card authorisation, used to re-create the subscription"
    )
    provider_plan = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    day_of_month = models.PositiveSmallIntegerField(null=True, blank=True)
    next_charge_date = models.DateField(null=True, blank=True)
    appeal_code = models.CharField(max_length=40, blank=True)
    emergency = models.ForeignKey("emergencies.EmergencyPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {self.display_amount}/month · {self.get_status_display()}"

    @property
    def display_amount(self):
        return money(self.amount, self.currency)


def _receipt_number():
    last = Receipt.objects.order_by("-number").values_list("number", flat=True).first()
    return (last or 1000) + 1


class Receipt(models.Model):
    donation = models.OneToOneField(Donation, on_delete=models.CASCADE, related_name="receipt")
    number = models.PositiveIntegerField(unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]

    def __str__(self):
        return f"Receipt {self.display_number}"

    @property
    def display_number(self):
        return f"R{self.number:06d}"

    @classmethod
    def for_donation(cls, donation):
        existing = cls.objects.filter(donation=donation).first()
        if existing:
            return existing
        from django.db import IntegrityError, transaction

        for _ in range(5):
            try:
                with transaction.atomic():
                    return cls.objects.create(donation=donation, number=_receipt_number())
            except IntegrityError:
                continue
        raise RuntimeError("Could not allocate a receipt number")


# --- Tributes and e-cards ------------------------------------------------------


class ECard(models.Model):
    TYPE_CHOICES = [("honor", "In honour of"), ("memory", "In memory of"), ("gift", "Gift")]
    DESIGN_CHOICES = [("hope", "Hope (blue)"), ("bloom", "Bloom (green)"), ("light", "Light (gold)")]
    STATUS_CHOICES = [("scheduled", "Scheduled"), ("sent", "Sent"), ("failed", "Failed"), ("cancelled", "Cancelled")]

    donation = models.ForeignKey(Donation, null=True, blank=True, on_delete=models.CASCADE, related_name="ecards")
    gift_order = models.ForeignKey("giving.GiftOrder", null=True, blank=True, on_delete=models.CASCADE, related_name="ecards")
    card_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="honor")
    honoree_name = models.CharField(max_length=160, blank=True)
    sender_name = models.CharField(max_length=160, help_text="E-cards are never anonymous")
    recipient_name = models.CharField(max_length=160)
    recipient_email = models.EmailField()
    message = models.TextField(max_length=1000, blank=True)
    design = models.CharField(max_length=10, choices=DESIGN_CHOICES, default="hope")
    send_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="scheduled", db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["send_at"]
        verbose_name = "e-card"

    def __str__(self):
        return f"E-card to {self.recipient_email} ({self.get_status_display()})"

    @property
    def is_paid(self):
        if self.donation_id:
            return self.donation.status == "succeeded"
        if self.gift_order_id:
            return self.gift_order.status == "paid"
        return False

    @property
    def editable(self):
        return self.status == "scheduled"

    def owner_email(self):
        if self.donation_id:
            return self.donation.email
        if self.gift_order_id:
            return self.gift_order.email
        return ""


# --- Gifts catalog --------------------------------------------------------------


class GiftItem(index.Indexed, models.Model):
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    price_ngn = models.DecimalField(max_digits=12, decimal_places=2)
    price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    image = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    blurb = models.TextField()
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    panels = [
        FieldPanel("title"),
        FieldPanel("slug"),
        FieldRowPanel([FieldPanel("price_ngn"), FieldPanel("price_usd")]),
        FieldPanel("image"),
        FieldPanel("blurb"),
        FieldRowPanel([FieldPanel("active"), FieldPanel("order")]),
    ]
    search_fields = [index.SearchField("title"), index.AutocompleteField("title")]

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def price(self, currency):
        return self.price_ngn if currency == "NGN" else self.price_usd

    def display_price(self, currency):
        return money(self.price(currency), currency)


class GiftOrder(models.Model):
    STATUS_CHOICES = [("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"), ("refunded", "Refunded")]

    reference = models.CharField(max_length=30, unique=True, default=make_order_reference)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField(db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="gift_orders")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    donation = models.OneToOneField(Donation, null=True, blank=True, on_delete=models.SET_NULL, related_name="gift_order")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {self.display_total}"

    @property
    def display_total(self):
        return money(self.total, self.currency)


class GiftOrderLine(models.Model):
    order = models.ForeignKey(GiftOrder, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(GiftItem, null=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class GiftsCatalogPage(BasePage):
    intro = RichTextField(features=RICH_FEATURES, blank=True)
    faq_heading = models.CharField(max_length=120, default="Frequently asked questions")
    appeal_code = models.CharField(max_length=40, default="GIFTS")

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("intro"),
        FieldPanel("appeal_code"),
        FieldPanel("faq_heading"),
        InlinePanel("faqs", label="Question"),
    ]
    max_count = 1
    subpage_types = []

    class Meta:
        verbose_name = "Gifts catalog page"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx["items"] = GiftItem.objects.filter(active=True).select_related("image")
        return ctx


class GiftsFAQ(Orderable):
    page = ParentalKey(GiftsCatalogPage, on_delete=models.CASCADE, related_name="faqs")
    question = models.CharField(max_length=255)
    answer = RichTextField(features=RICH_FEATURES)

    panels = [FieldPanel("question"), FieldPanel("answer")]
