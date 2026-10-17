from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel, PageChooserPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page
from wagtail.search import index

from apps.core.blocks import RICH_FEATURES, body_blocks
from apps.core.models import BasePage


class HomePage(BasePage):
    hero_appeal = models.TextField(blank=True, help_text="Short appeal paragraph under the headline")
    hero_button_label = models.CharField(max_length=40, default="Give now")
    hero_appeal_code = models.CharField(max_length=40, default="HOME-HERO")

    mission_text = RichTextField(features=["bold", "italic", "link"], blank=True)
    mission_link = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    mission_link_label = models.CharField(max_length=60, default="Learn about our approach")

    impact_heading = models.CharField(max_length=120, default="Our Impact Around the World")

    donate_heading = models.CharField(max_length=160, default="Help Rush Emergency Relief to Those Who Need it Most")
    donate_text = models.TextField(blank=True)
    donate_appeal_code = models.CharField(max_length=40, default="HOME-BAND")

    stories_heading = models.CharField(max_length=120, default="Stories of Hope. Thanks to You.")
    community_heading = models.CharField(max_length=120, default="Join Our Community")
    community_text = models.TextField(blank=True)
    body = StreamField(body_blocks(), blank=True, use_json_field=True, help_text="Optional extra sections")

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_image"),
                FieldPanel("hero_heading"),
                FieldPanel("hero_appeal"),
                FieldRowPanel([FieldPanel("hero_button_label"), FieldPanel("hero_appeal_code")]),
            ],
            heading="Hero (the emergency cards under it come from active emergencies marked 'featured')",
        ),
        MultiFieldPanel(
            [FieldPanel("mission_text"), FieldRowPanel([FieldPanel("mission_link"), FieldPanel("mission_link_label")])],
            heading="Mission statement",
        ),
        FieldPanel("impact_heading"),
        InlinePanel("impact_rows", label="Impact row"),
        MultiFieldPanel(
            [FieldPanel("donate_heading"), FieldPanel("donate_text"), FieldPanel("donate_appeal_code")],
            heading="Donate band",
        ),
        FieldPanel("stories_heading"),
        MultiFieldPanel([FieldPanel("community_heading"), FieldPanel("community_text")], heading="Newsletter"),
        FieldPanel("body"),
    ]
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]

    class Meta:
        verbose_name = "Homepage"

    def get_context(self, request, *args, **kwargs):
        from apps.emergencies.models import EmergencyPage
        from apps.stories.models import StoryPage

        ctx = super().get_context(request, *args, **kwargs)
        ctx["hero_emergencies"] = (
            EmergencyPage.objects.live().public().filter(status="active").order_by("-featured", "-year_start")[:3]
        )
        ctx["latest_stories"] = StoryPage.objects.live().public().filter(story_type="story").order_by("-date")[:3]
        return ctx


class HomeImpactRow(Orderable):
    page = ParentalKey(HomePage, on_delete=models.CASCADE, related_name="impact_rows")
    image = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    headline = models.CharField(max_length=160, help_text="Stat headline, e.g. 'Helping 15 million people in 2025'")
    text = RichTextField(features=["bold", "italic", "link"])
    link_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    link_label = models.CharField(max_length=60, default="Learn more")

    panels = [
        FieldPanel("image"),
        FieldPanel("headline"),
        FieldPanel("text"),
        FieldRowPanel([FieldPanel("link_page"), FieldPanel("link_label")]),
    ]


class StandardPage(BasePage):
    """Flexible page built from blocks: hubs, Mission, Values, legal pages, Get Involved pages…"""

    body = StreamField(body_blocks(), blank=True, use_json_field=True)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [FieldPanel("body")]
    search_fields = BasePage.search_fields + [index.SearchField("body"), index.SearchField("hero_intro")]

    class Meta:
        verbose_name = "Standard page"


class FAQPage(BasePage):
    intro = RichTextField(features=RICH_FEATURES, blank=True)
    side_heading = models.CharField(max_length=120, default="Contact us")
    side_text = RichTextField(features=["bold", "italic", "link"], blank=True)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("intro"),
        InlinePanel("faqs", label="Question"),
        MultiFieldPanel([FieldPanel("side_heading"), FieldPanel("side_text")], heading="Side box"),
    ]
    search_fields = BasePage.search_fields + [index.SearchField("intro")]
    max_count = 1
    subpage_types = []

    class Meta:
        verbose_name = "FAQ page"


class FAQItem(Orderable):
    page = ParentalKey(FAQPage, on_delete=models.CASCADE, related_name="faqs")
    question = models.CharField(max_length=255)
    answer = RichTextField(features=RICH_FEATURES)

    panels = [FieldPanel("question"), FieldPanel("answer")]


class Office(models.Model):
    name = models.CharField(max_length=120)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    fax = models.CharField(max_length=40, blank=True)
    emails = models.TextField(blank=True, help_text="One per line, optionally 'Label: email'")
    order = models.PositiveIntegerField(default=0)

    panels = [
        FieldPanel("name"),
        FieldPanel("address"),
        FieldRowPanel([FieldPanel("phone"), FieldPanel("fax")]),
        FieldPanel("emails"),
        FieldPanel("order"),
    ]

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def email_list(self):
        rows = []
        for line in self.emails.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line and "@" in line.split(":", 1)[1]:
                label, email = line.split(":", 1)
                rows.append((label.strip(), email.strip()))
            else:
                rows.append(("", line))
        return rows


class ContactPage(BasePage):
    intro = RichTextField(features=RICH_FEATURES, blank=True)
    departments_heading = models.CharField(max_length=120, default="Departments")

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("intro"),
        FieldPanel("departments_heading"),
        InlinePanel("departments", label="Department email"),
    ]
    max_count = 1
    subpage_types = []

    class Meta:
        verbose_name = "Contact page"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx["offices"] = Office.objects.all()
        return ctx


class DepartmentEmail(Orderable):
    page = ParentalKey(ContactPage, on_delete=models.CASCADE, related_name="departments")
    label = models.CharField(max_length=120, help_text="e.g. Donations, Media, Events")
    email = models.EmailField()

    panels = [FieldRowPanel([FieldPanel("label"), FieldPanel("email")])]
