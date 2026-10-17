from django.db import models
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel
from wagtail.search import index


class Resource(index.Indexed, models.Model):
    KIND_CHOICES = [
        ("capability", "Capability statement"),
        ("assessment", "Assessment"),
        ("toolkit", "Toolkit / guidelines"),
        ("webinar", "Webinar"),
        ("press", "Press release"),
        ("report", "Report"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=255)
    date = models.DateField()
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="other")
    document = models.ForeignKey("wagtaildocs.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    url = models.URLField(blank=True, help_text="External link, used if no document is chosen")
    programs = models.ManyToManyField("programs.ProgramPage", blank=True, related_name="resources")
    countries = models.ManyToManyField("countries.CountryPage", blank=True, related_name="resources")
    emergencies = models.ManyToManyField("emergencies.EmergencyPage", blank=True, related_name="resources")

    panels = [
        FieldPanel("title"),
        FieldRowPanel([FieldPanel("date"), FieldPanel("kind")]),
        FieldPanel("document"),
        FieldPanel("url"),
        MultiFieldPanel(
            [FieldPanel("programs"), FieldPanel("countries"), FieldPanel("emergencies")],
            heading="Show on",
        ),
    ]
    search_fields = [index.SearchField("title"), index.AutocompleteField("title")]

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.title

    @property
    def href(self):
        return self.document.url if self.document else self.url

    @property
    def is_external(self):
        return not self.document and bool(self.url)
