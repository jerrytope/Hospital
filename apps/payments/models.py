from django.db import models


class WebhookEvent(models.Model):
    """Every provider webhook we receive. The unique event id makes retries harmless."""

    provider = models.CharField(max_length=10)
    event_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="unique_provider_event")]

    def __str__(self):
        return f"{self.provider}:{self.event_type}:{self.event_id}"

    @property
    def ok(self):
        return self.processed_at is not None and not self.error
