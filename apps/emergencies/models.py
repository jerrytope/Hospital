from django.db import models
from django.utils.text import slugify
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable
from wagtail.search import index

from apps.core.blocks import RICH_FEATURES, IconStatBlock, body_blocks
from apps.core.models import BasePage


class CountryResponseBlock(blocks.StructBlock):
    """'Our Response' for one country, with sub-headings for each type of work."""

    country = blocks.PageChooserBlock(page_type="countries.CountryPage", required=False)
    heading = blocks.CharBlock(help_text="e.g. Democratic Republic of the Congo")
    intro = blocks.RichTextBlock(features=RICH_FEATURES, required=False)
    sections = blocks.ListBlock(
        blocks.StructBlock(
            [("heading", blocks.CharBlock()), ("text", blocks.RichTextBlock(features=RICH_FEATURES))]
        ),
        required=False,
        default=[],
    )

    class Meta:
        icon = "site"
        template = "blocks/country_response.html"


class EmergencyPage(BasePage):
    """/emergency-response/<slug>/ — the emergency hub, the most complex template."""

    STATUS_CHOICES = [("active", "Active"), ("ongoing", "Ongoing crisis"), ("past", "Past")]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    featured = models.BooleanField(default=False, help_text="Show first on the homepage and in the menu")
    year_start = models.PositiveIntegerField(null=True, blank=True)
    year_end = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank while ongoing")
    countries = ParentalManyToManyField("countries.CountryPage", blank=True, related_name="emergencies")
    programs = ParentalManyToManyField("programs.ProgramPage", blank=True, related_name="emergencies")
    card_summary = models.CharField(max_length=255, blank=True, help_text="One line used on cards")

    summary = RichTextField(features=RICH_FEATURES, blank=True, help_text="Situation summary")
    donate_heading = models.CharField(max_length=160, default="Help us respond now")
    donate_text = models.TextField(blank=True)
    appeal_code = models.CharField(
        max_length=40, blank=True, help_text="Donations from this page are tagged with this code and this emergency"
    )
    key_facts = StreamField([("fact", IconStatBlock())], blank=True, use_json_field=True)
    response_heading = models.CharField(max_length=120, default="Our Response")
    responses = StreamField([("country", CountryResponseBlock())], blank=True, use_json_field=True)
    history = RichTextField("History", features=RICH_FEATURES, blank=True)
    expertise = RichTextField("Expertise", features=RICH_FEATURES, blank=True)
    featured_stories = ParentalManyToManyField("stories.StoryPage", blank=True, related_name="+")
    body = StreamField(body_blocks(), blank=True, use_json_field=True, help_text="Optional extra sections")

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("status"), FieldPanel("featured")]),
                FieldRowPanel([FieldPanel("year_start"), FieldPanel("year_end")]),
                FieldPanel("countries"),
                FieldPanel("programs"),
                FieldPanel("card_summary"),
            ],
            heading="Emergency details",
        ),
        FieldPanel("summary"),
        MultiFieldPanel(
            [FieldPanel("donate_heading"), FieldPanel("donate_text"), FieldPanel("appeal_code")],
            heading="Emergency donate call-out",
        ),
        FieldPanel("key_facts"),
        FieldPanel("response_heading"),
        FieldPanel("responses"),
        FieldPanel("history"),
        FieldPanel("expertise"),
        InlinePanel("faqs", label="FAQ"),
        FieldPanel("featured_stories"),
        FieldPanel("body"),
    ]
    search_fields = BasePage.search_fields + [index.SearchField("summary"), index.SearchField("card_summary")]
    parent_page_types = ["core.FolderPage"]
    subpage_types = ["pages.StandardPage"]

    class Meta:
        verbose_name = "Emergency page"

    @property
    def year_label(self):
        if self.status == "ongoing" and not self.year_end:
            return "ONGOING"
        if self.year_start and self.year_end and self.year_end != self.year_start:
            return f"{self.year_start}–{self.year_end}"
        return str(self.year_start or "")

    def anchor_nav(self, ctx):
        nav = []
        for block in self.responses:
            nav.append((slugify(block.value["heading"]), block.value["heading"]))
        if self.history:
            nav.append(("history", "History"))
        if self.expertise:
            nav.append(("expertise", "Expertise"))
        if self.faqs.exists():
            nav.append(("faq", "FAQ"))
        if ctx["media_alerts"]:
            nav.append(("media-alerts", "Media Alerts"))
        if ctx["sitreps"]:
            nav.append(("situation-reports", "Situation Reports"))
        if ctx["resources"]:
            nav.append(("resources", "Resources"))
        return nav

    def get_context(self, request, *args, **kwargs):
        from apps.resources.models import Resource
        from apps.stories.models import StoryPage

        ctx = super().get_context(request, *args, **kwargs)
        ctx["media_alerts"] = list(self.media_alerts.order_by("-date")[:20])
        ctx["sitreps"] = list(self.situation_reports.order_by("-date", "-number")[:20])
        ctx["resources"] = list(Resource.objects.filter(emergencies=self).order_by("-date")[:20])
        ctx["featured"] = self.featured_stories.live().public()[:2]
        ctx["related_stories"] = StoryPage.objects.live().public().filter(emergencies=self).order_by("-date")[:3]
        ctx["anchor_nav"] = self.anchor_nav(ctx)
        from apps.giving.models import DonationSettings

        ds = DonationSettings.load(request_or_site=request)
        ctx["emergency_currency"] = ds.default_currency
        ctx["emergency_presets"] = ds.presets(ds.default_currency)[:3]
        return ctx


class EmergencyFAQ(Orderable):
    page = ParentalKey(EmergencyPage, on_delete=models.CASCADE, related_name="faqs")
    question = models.CharField(max_length=255)
    answer = RichTextField(features=RICH_FEATURES)

    panels = [FieldPanel("question"), FieldPanel("answer")]


class EmergencyIndexPage(BasePage):
    """/what-we-do/emergencies/ — active, ongoing and past emergencies."""

    intro = RichTextField(features=RICH_FEATURES, blank=True)
    active_heading = models.CharField(max_length=120, default="Active Emergencies")
    ongoing_heading = models.CharField(max_length=120, default="Ongoing Crises")
    past_heading = models.CharField(max_length=120, default="Past Emergencies")
    initial_past_rows = models.PositiveIntegerField(default=15, help_text="Rows shown before 'See all past emergencies'")

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("intro"),
        FieldPanel("active_heading"),
        FieldPanel("ongoing_heading"),
        FieldPanel("past_heading"),
        FieldPanel("initial_past_rows"),
    ]
    max_count = 1
    subpage_types = []

    class Meta:
        verbose_name = "Emergencies list page"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        live = EmergencyPage.objects.live().public()
        ctx["active"] = live.filter(status="active").order_by("-featured", "-year_start", "title")
        ctx["ongoing"] = live.filter(status="ongoing").prefetch_related("countries").order_by("-year_start", "title")
        ctx["past_rows"] = PastEmergency.objects.select_related("page").all()
        return ctx


class PastEmergency(models.Model):
    """A row in the past-emergencies table. Rows link to a page or expand to show text."""

    country = models.CharField(max_length=120)
    name = models.CharField("Emergency", max_length=160)
    year = models.CharField(max_length=20)
    page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    details = RichTextField(features=["bold", "italic", "link"], blank=True, help_text="Shown when the row is expanded (used when there is no page)")
    order = models.PositiveIntegerField(default=0)

    panels = [
        FieldRowPanel([FieldPanel("country"), FieldPanel("year")]),
        FieldPanel("name"),
        FieldPanel("page"),
        FieldPanel("details"),
        FieldPanel("order"),
    ]

    class Meta:
        ordering = ["order", "-year", "country"]
        verbose_name = "past emergency row"

    def __str__(self):
        return f"{self.country} — {self.name} ({self.year})"


class SituationReport(models.Model):
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField(null=True, blank=True)
    date = models.DateField()
    document = models.ForeignKey("wagtaildocs.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    emergency = models.ForeignKey(EmergencyPage, null=True, blank=True, on_delete=models.CASCADE, related_name="situation_reports")
    country = models.ForeignKey("countries.CountryPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="situation_reports")

    panels = [
        FieldPanel("title"),
        FieldRowPanel([FieldPanel("number"), FieldPanel("date")]),
        FieldPanel("document"),
        FieldPanel("emergency"),
        FieldPanel("country"),
    ]

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.title


class MediaAlert(models.Model):
    date = models.DateField()
    outlet = models.CharField(max_length=120)
    headline = models.CharField(max_length=255)
    url = models.URLField(blank=True)
    video_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    emergency = models.ForeignKey(EmergencyPage, null=True, blank=True, on_delete=models.CASCADE, related_name="media_alerts")

    panels = [
        FieldRowPanel([FieldPanel("date"), FieldPanel("outlet")]),
        FieldPanel("headline"),
        FieldPanel("url"),
        FieldPanel("video_page"),
        FieldPanel("emergency"),
    ]

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.outlet}: {self.headline}"

    @property
    def href(self):
        return self.video_page.url if self.video_page else self.url
