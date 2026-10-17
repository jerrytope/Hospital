from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable
from wagtail.search import index

from apps.core.blocks import RICH_FEATURES, LinkCardsBlock, body_blocks
from apps.core.models import BasePage


class HistoryPage(BasePage):
    intro = RichTextField(features=RICH_FEATURES, blank=True)
    end_links = StreamField([("cards", LinkCardsBlock())], blank=True, use_json_field=True, max_num=1)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("intro"),
        InlinePanel("timeline_entries", label="Timeline entry"),
        FieldPanel("end_links"),
    ]
    max_count = 1
    subpage_types = []

    class Meta:
        verbose_name = "History page"


class TimelineEntry(Orderable):
    page = ParentalKey(HistoryPage, on_delete=models.CASCADE, related_name="timeline_entries")
    year = models.CharField(max_length=20)
    title = models.CharField(max_length=160, help_text="Place or title")
    text = RichTextField(features=["bold", "italic", "link"])
    photo = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    featured = models.BooleanField(default=False, help_text="Show in the 'Our Rich History' teaser")

    panels = [
        FieldRowPanel([FieldPanel("year"), FieldPanel("featured")]),
        FieldPanel("title"),
        FieldPanel("text"),
        FieldPanel("photo"),
    ]


class Person(index.Indexed, models.Model):
    GROUP_CHOICES = [
        ("featured", "Featured (founder / CEO, shown with photo and bio)"),
        ("board", "Board of Directors"),
        ("council", "Leadership Council"),
        ("ambassador", "Global Ambassadors"),
        ("executive", "Executive Staff"),
        ("affiliate", "Affiliate board"),
    ]

    name = models.CharField(max_length=120)
    title = models.CharField(max_length=160, blank=True)
    group = models.CharField(max_length=20, choices=GROUP_CHOICES)
    affiliate_name = models.CharField(max_length=120, blank=True, help_text="For affiliate boards, e.g. 'UK Board'")
    company = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=120, blank=True)
    bio = RichTextField(features=["bold", "italic", "link"], blank=True)
    photo = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    order = models.PositiveIntegerField(default=0)

    panels = [
        FieldRowPanel([FieldPanel("name"), FieldPanel("title")]),
        FieldRowPanel([FieldPanel("group"), FieldPanel("affiliate_name")]),
        FieldRowPanel([FieldPanel("company"), FieldPanel("city")]),
        FieldPanel("bio"),
        FieldPanel("photo"),
        FieldPanel("order"),
    ]
    search_fields = [index.SearchField("name"), index.AutocompleteField("name"), index.FilterField("group")]

    class Meta:
        ordering = ["group", "order", "name"]
        verbose_name_plural = "people"

    def __str__(self):
        return self.name


class LeadershipPage(BasePage):
    intro = RichTextField(features=RICH_FEATURES, blank=True)
    end_links = StreamField([("cards", LinkCardsBlock())], blank=True, use_json_field=True, max_num=1)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [FieldPanel("intro"), FieldPanel("end_links")]
    max_count = 1
    subpage_types = []

    class Meta:
        verbose_name = "Leadership page"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        people = Person.objects.select_related("photo").all()
        groups = {key: [] for key, _ in Person.GROUP_CHOICES}
        for p in people:
            groups[p.group].append(p)
        affiliates = {}
        for p in groups["affiliate"]:
            affiliates.setdefault(p.affiliate_name or "Affiliate board", []).append(p)
        labels = dict(Person.GROUP_CHOICES)
        ctx["featured_people"] = groups["featured"]
        ctx["groups"] = [(labels[k], groups[k], k) for k in ("board", "council", "ambassador", "executive") if groups[k]]
        ctx["affiliate_groups"] = affiliates.items()
        return ctx


class Report(models.Model):
    TYPE_CHOICES = [
        ("annual", "Annual report"),
        ("impact", "Impact report"),
        ("audit", "Audited financial statements"),
        ("tax", "Tax return form"),
    ]

    report_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    year = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    cover = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    document = models.ForeignKey("wagtaildocs.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    panels = [
        FieldRowPanel([FieldPanel("report_type"), FieldPanel("year")]),
        FieldPanel("title"),
        FieldPanel("summary"),
        FieldPanel("cover"),
        FieldPanel("document"),
    ]

    class Meta:
        ordering = ["-year", "report_type"]

    def __str__(self):
        return f"{self.title} ({self.year})"


class FinancialReportsPage(BasePage):
    efficiency_value = models.CharField(max_length=20, blank=True, help_text="e.g. 91%")
    efficiency_text = models.CharField(max_length=255, blank=True, help_text="e.g. of our budget goes directly to programs")
    efficiency_image = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ratings_text = RichTextField(features=RICH_FEATURES, blank=True, help_text="Charity ratings and memberships")
    body = StreamField(body_blocks(), blank=True, use_json_field=True)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        MultiFieldPanel(
            [FieldPanel("efficiency_value"), FieldPanel("efficiency_text"), FieldPanel("efficiency_image")],
            heading="Efficiency headline",
        ),
        FieldPanel("ratings_text"),
        FieldPanel("body"),
    ]
    max_count = 1
    subpage_types = []

    class Meta:
        verbose_name = "Financial reports page"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        annual = list(Report.objects.filter(report_type="annual"))
        ctx["latest_annual"] = annual[0] if annual else None
        ctx["older_annual"] = annual[1:]
        ctx["impact_reports"] = Report.objects.filter(report_type="impact")
        by_year = {}
        for r in Report.objects.filter(report_type__in=["audit", "tax"]):
            by_year.setdefault(r.year, []).append(r)
        ctx["financial_by_year"] = sorted(by_year.items(), reverse=True)
        return ctx
