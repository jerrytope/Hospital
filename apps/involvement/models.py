from datetime import timedelta

from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable
from wagtail.search import index

from apps.core.blocks import RICH_FEATURES
from apps.core.models import BasePage


class Event(index.Indexed, models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    place = models.CharField(max_length=200, blank=True)
    description = RichTextField(features=RICH_FEATURES, blank=True)
    image = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ticket_url = models.URLField(blank=True)

    panels = [
        FieldPanel("title"),
        FieldRowPanel([FieldPanel("start"), FieldPanel("end")]),
        FieldPanel("place"),
        FieldPanel("description"),
        FieldPanel("image"),
        FieldPanel("ticket_url"),
    ]
    search_fields = [index.SearchField("title"), index.AutocompleteField("title")]

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return self.title

    @property
    def is_upcoming(self):
        return (self.end or self.start) >= timezone.now()


class Tender(index.Indexed, ClusterableModel):
    title = models.CharField(max_length=200)
    reference = models.CharField(max_length=60, blank=True)
    country = models.CharField(max_length=120, blank=True)
    deadline = models.DateTimeField()
    description = RichTextField(features=RICH_FEATURES, blank=True)
    published = models.BooleanField(default=True)

    panels = [
        FieldRowPanel([FieldPanel("title"), FieldPanel("reference")]),
        FieldRowPanel([FieldPanel("country"), FieldPanel("deadline")]),
        FieldPanel("description"),
        InlinePanel("documents", label="Tender document"),
        FieldPanel("published"),
    ]
    search_fields = [index.SearchField("title"), index.AutocompleteField("title")]

    class Meta:
        ordering = ["deadline"]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.deadline >= timezone.now()


class TenderDocument(Orderable):
    tender = ParentalKey(Tender, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200)
    document = models.ForeignKey("wagtaildocs.Document", on_delete=models.CASCADE, related_name="+")

    panels = [FieldPanel("title"), FieldPanel("document")]


class Job(index.Indexed, models.Model):
    TYPE_CHOICES = [
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contract", "Contract"),
        ("consultancy", "Consultancy"),
        ("volunteer", "Volunteer"),
        ("internship", "Internship"),
    ]

    title = models.CharField(max_length=200)
    location = models.CharField(max_length=160)
    job_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default="full_time")
    deadline = models.DateField(null=True, blank=True)
    summary = models.TextField(blank=True)
    description = RichTextField(features=RICH_FEATURES, blank=True)
    apply_url = models.URLField(blank=True, help_text="Application form or job board link")
    apply_email = models.EmailField(blank=True)
    published = models.BooleanField(default=True)

    panels = [
        FieldPanel("title"),
        FieldRowPanel([FieldPanel("location"), FieldPanel("job_type")]),
        FieldPanel("deadline"),
        FieldPanel("summary"),
        FieldPanel("description"),
        FieldRowPanel([FieldPanel("apply_url"), FieldPanel("apply_email")]),
        FieldPanel("published"),
    ]
    search_fields = [index.SearchField("title"), index.AutocompleteField("title")]

    class Meta:
        ordering = ["deadline", "title"]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return not self.deadline or self.deadline >= timezone.localdate()


class ListingPage(BasePage):
    """Events, Open Tenders or Work With Us list page, fed by the matching snippets."""

    KIND_CHOICES = [("events", "Events"), ("tenders", "Open tenders"), ("jobs", "Jobs")]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    intro = RichTextField(features=RICH_FEATURES, blank=True)
    empty_text = models.CharField(max_length=255, default="There are no open listings right now. Please check back soon.")

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("kind"),
        FieldPanel("intro"),
        FieldPanel("empty_text"),
    ]
    subpage_types = []

    class Meta:
        verbose_name = "Events / tenders / jobs list page"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        now = timezone.now()
        if self.kind == "events":
            ctx["upcoming"] = Event.objects.filter(start__gte=now - timedelta(days=1))
            ctx["past"] = Event.objects.filter(start__lt=now - timedelta(days=1)).order_by("-start")[:6]
        elif self.kind == "tenders":
            qs = Tender.objects.filter(published=True).prefetch_related("documents__document")
            ctx["open_items"] = qs.filter(deadline__gte=now)
            ctx["closed_items"] = qs.filter(deadline__lt=now).order_by("-deadline")[:10]
        else:
            qs = Job.objects.filter(published=True)
            today = timezone.localdate()
            ctx["open_items"] = [j for j in qs if not j.deadline or j.deadline >= today]
        return ctx
