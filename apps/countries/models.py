from django.db import models
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable
from wagtail.search import index

from apps.core.blocks import RICH_FEATURES, body_blocks
from apps.core.icons import ICON_CHOICES
from apps.core.models import BasePage


class CountryPage(BasePage):
    """/country/<slug>/ — a country where the charity works or has worked."""

    STATUS_CHOICES = [("current", "Current"), ("past", "Past")]

    region = models.ForeignKey("taxonomy.Region", null=True, blank=True, on_delete=models.SET_NULL, related_name="countries")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="current")
    has_detail_page = models.BooleanField(
        default=True, help_text="Untick for past countries that are listed as plain text only"
    )
    work_started = models.PositiveIntegerField(null=True, blank=True, help_text="Year work began")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    programs = ParentalManyToManyField("programs.ProgramPage", blank=True, related_name="countries")

    featured_emergency = models.ForeignKey(
        "emergencies.EmergencyPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    intro = RichTextField(features=RICH_FEATURES, blank=True)

    population = models.CharField(max_length=40, blank=True, help_text="e.g. 223.8 million")
    life_expectancy = models.CharField(max_length=40, blank=True, help_text="e.g. 54 years")
    infant_mortality = models.CharField(max_length=60, blank=True, help_text="e.g. 69 per 1,000 live births")

    award_heading = models.CharField(max_length=120, blank=True, help_text="Optional award or profile feature")
    award_text = RichTextField(features=["bold", "italic", "link"], blank=True)

    challenges_heading = models.CharField(max_length=120, default="The Challenges")
    response_heading = models.CharField(max_length=120, default="Our Response")
    response_intro = RichTextField(features=RICH_FEATURES, blank=True)
    impact_year = models.PositiveIntegerField(null=True, blank=True)
    body = StreamField(body_blocks(), blank=True, use_json_field=True, help_text="Optional extra sections")
    appeal_code = models.CharField(max_length=40, blank=True)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("region"), FieldPanel("status")]),
                FieldPanel("has_detail_page"),
                FieldPanel("work_started"),
                FieldRowPanel([FieldPanel("latitude"), FieldPanel("longitude")]),
                FieldPanel("programs"),
            ],
            heading="Country details",
        ),
        FieldPanel("featured_emergency"),
        FieldPanel("intro"),
        MultiFieldPanel(
            [FieldPanel("population"), FieldPanel("life_expectancy"), FieldPanel("infant_mortality")],
            heading="Key stats",
        ),
        MultiFieldPanel([FieldPanel("award_heading"), FieldPanel("award_text")], heading="Award / profile feature"),
        FieldPanel("challenges_heading"),
        InlinePanel("challenges", label="Challenge", max_num=6),
        FieldPanel("response_heading"),
        FieldPanel("response_intro"),
        InlinePanel("response_sectors", label="Response sector"),
        FieldPanel("impact_year"),
        InlinePanel("impact_stats", label="Impact number", max_num=4),
        FieldPanel("body"),
        FieldPanel("appeal_code"),
    ]
    search_fields = BasePage.search_fields + [index.SearchField("intro")]
    parent_page_types = ["core.FolderPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Country page"
        ordering = ["title"]

    def get_context(self, request, *args, **kwargs):
        from apps.emergencies.models import SituationReport
        from apps.resources.models import Resource
        from apps.stories.models import StoryPage

        ctx = super().get_context(request, *args, **kwargs)
        ctx["related_stories"] = StoryPage.objects.live().public().filter(countries=self).order_by("-date")[:3]
        ctx["resources"] = Resource.objects.filter(countries=self).order_by("-date")[:12]
        ctx["sitreps"] = SituationReport.objects.filter(country=self).order_by("-date")[:12]
        siblings = list(
            CountryPage.objects.live().public().filter(status="current", has_detail_page=True).order_by("title")
        )
        if self in siblings and len(siblings) > 1:
            i = siblings.index(self)
            ctx["prev_country"] = siblings[i - 1]
            ctx["next_country"] = siblings[(i + 1) % len(siblings)]
        ctx["other_countries"] = [c for c in siblings if c.pk != self.pk and c.region_id == self.region_id][:6]
        return ctx


class Challenge(Orderable):
    page = ParentalKey(CountryPage, on_delete=models.CASCADE, related_name="challenges")
    icon = models.CharField(max_length=40, choices=ICON_CHOICES, default="shield-alert")
    title = models.CharField(max_length=120)
    text = models.CharField(max_length=255, blank=True)

    panels = [FieldPanel("icon"), FieldPanel("title"), FieldPanel("text")]


class ResponseSector(Orderable):
    page = ParentalKey(CountryPage, on_delete=models.CASCADE, related_name="response_sectors")
    icon = models.CharField(max_length=40, choices=ICON_CHOICES, default="heart-pulse")
    title = models.CharField(max_length=120)
    text = RichTextField(features=RICH_FEATURES)

    panels = [FieldPanel("icon"), FieldPanel("title"), FieldPanel("text")]


class CountryImpactStat(Orderable):
    page = ParentalKey(CountryPage, on_delete=models.CASCADE, related_name="impact_stats")
    value = models.CharField(max_length=40, help_text="e.g. 1.2 million")
    label = models.CharField(max_length=120)

    panels = [FieldPanel("value"), FieldPanel("label")]


class WhereWeWorkPage(BasePage):
    """/where-we-work/ — map plus lists of current and past countries."""

    intro = RichTextField(features=RICH_FEATURES, blank=True)
    current_heading = models.CharField(max_length=120, default="Where we work today")
    past_heading = models.CharField(max_length=120, default="Where we have worked")
    body = StreamField(body_blocks(), blank=True, use_json_field=True)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("intro"),
        FieldPanel("current_heading"),
        FieldPanel("past_heading"),
        FieldPanel("body"),
    ]
    max_count = 1
    subpage_types = ["pages.StandardPage"]

    def get_context(self, request, *args, **kwargs):
        from apps.taxonomy.models import Region

        ctx = super().get_context(request, *args, **kwargs)
        countries = CountryPage.objects.live().public().select_related("region").order_by("title")
        ctx["regions"] = Region.objects.all()
        ctx["current_countries"] = [c for c in countries if c.status == "current"]
        ctx["past_countries"] = [c for c in countries if c.status == "past"]
        ctx["map_points"] = [
            {
                "name": c.title,
                "url": c.url if c.has_detail_page else "",
                "lat": float(c.latitude),
                "lng": float(c.longitude),
                "region": c.region.slug if c.region else "",
                "status": c.status,
            }
            for c in countries
            if c.latitude is not None and c.longitude is not None
        ]
        return ctx
