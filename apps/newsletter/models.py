from django.conf import settings
from django.core import signing
from django.db import models
from django.urls import reverse


class Subscriber(models.Model):
    STATUS_CHOICES = [("subscribed", "Subscribed"), ("unsubscribed", "Unsubscribed")]
    SYNC_CHOICES = [("pending", "Pending"), ("synced", "Synced"), ("failed", "Failed"), ("skipped", "Not configured")]

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="subscribed")
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_text = models.TextField(blank=True, help_text="Exact consent wording shown when they signed up")
    source_page = models.CharField(max_length=500, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="subscriptions")
    sync_status = models.CharField(max_length=10, choices=SYNC_CHOICES, default="pending")
    sync_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def unsubscribe_token(self):
        return signing.dumps({"s": self.pk}, salt="newsletter-unsubscribe")

    def unsubscribe_url(self):
        return settings.SITE_URL + reverse("newsletter:unsubscribe", args=[self.unsubscribe_token()])

    @classmethod
    def from_token(cls, token):
        try:
            data = signing.loads(token, salt="newsletter-unsubscribe", max_age=60 * 60 * 24 * 365 * 3)
        except signing.BadSignature:
            return None
        return cls.objects.filter(pk=data.get("s")).first()
