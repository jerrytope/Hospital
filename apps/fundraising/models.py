from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.giving.models import CURRENCY_CHOICES, money


class Fundraiser(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Awaiting approval"),
        ("changes", "Changes requested"),
        ("live", "Live"),
        ("ended", "Ended"),
        ("hidden", "Hidden by staff"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fundraisers")
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    story = models.TextField(help_text="Why you are fundraising")
    photo = models.ImageField(upload_to="fundraisers/%Y/%m/", blank=True)
    goal = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="NGN")
    end_date = models.DateField(null=True, blank=True)
    emergency = models.ForeignKey(
        "emergencies.EmergencyPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="fundraisers",
        help_text="Optional: raise for a specific emergency",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft", db_index=True)
    ever_approved = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    staff_note = models.TextField(blank=True, help_text="Shown to the fundraiser when changes are requested")
    edited_since_review = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:120] or "fundraiser"
            slug, n = base, 2
            while Fundraiser.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("fundraising:detail", args=[self.slug])

    @property
    def is_public(self):
        return self.status in ("live", "ended")

    @property
    def is_accepting(self):
        return self.status == "live" and (not self.end_date or self.end_date >= timezone.localdate())

    @property
    def raised(self):
        total = self.donations.filter(status="succeeded", currency=self.currency).aggregate(t=Sum("amount"))["t"]
        return total or Decimal("0")

    @property
    def donor_count(self):
        return self.donations.filter(status="succeeded").count()

    @property
    def percent(self):
        if not self.goal:
            return 0
        return min(100, int(self.raised / self.goal * 100))

    @property
    def display_raised(self):
        return money(self.raised, self.currency)

    @property
    def display_goal(self):
        return money(self.goal, self.currency)


class FundraiserUpdate(models.Model):
    fundraiser = models.ForeignKey(Fundraiser, on_delete=models.CASCADE, related_name="updates")
    text = models.TextField(max_length=2000)
    photo = models.ImageField(upload_to="fundraisers/updates/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class FundraiserReport(models.Model):
    fundraiser = models.ForeignKey(Fundraiser, on_delete=models.CASCADE, related_name="reports")
    reason = models.TextField(max_length=1000)
    reporter_email = models.EmailField(blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["resolved", "-created_at"]
