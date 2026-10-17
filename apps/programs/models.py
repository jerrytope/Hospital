from django.db import models
from modelcluster.fields import ParentalKey
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.search import index

from apps.core.blocks import IconStatBlock, RICH_FEATURES, body_blocks
from apps.core.icons import ICON_CHOICES
from apps.core.models import BasePage


class ProgramPage(BasePage):
    """/program/<slug>/ — one of the charity's program areas."""

    short_description = models.CharField(max_length=255, blank=True, help_text="Used on cards and in menus")
    card_icon = models.CharField(max_length=40, choices=ICON_CHOICES, default="heart-pulse")
    intro = RichTextField(features=RICH_FEATURES, blank=True)
    icon_stats = StreamField([("stat", IconStatBlock())], blank=True, use_json_field=True, max_num=3)
    achievements_heading = models.CharField(max_length=120, blank=True, default="Our achievements")
    achievements = StreamField(
        [("item", blocks.TextBlock())], blank=True, use_json_field=True, help_text="Bullet list of achievements"
    )
    focus_heading = models.CharField(max_length=120, default="Areas of Focus")
    featured_resources = StreamField(
        [
            (
                "resource",
                blocks.StructBlock(
                    [
                        ("label", blocks.CharBlock(required=False, help_text="e.g. Guidelines, Webinar")),
                        ("title", blocks.CharBlock()),
                        ("text", blocks.TextBlock(required=False)),
                        ("image", ImageChooserBlock(required=False)),
                        ("document", DocumentChooserBlock(required=False)),
                        ("url", blocks.URLBlock(required=False, help_text="Video or external link")),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
        help_text="Featured guidelines, webinars and similar",
    )
    featured_story = models.ForeignKey(
        "stories.StoryPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = StreamField(body_blocks(), blank=True, use_json_field=True, help_text="Optional extra sections")
    donate_heading = models.CharField(max_length=120, default="Your gift can save lives")
    appeal_code = models.CharField(max_length=40, blank=True)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [
        FieldPanel("short_description"),
        FieldPanel("card_icon"),
        FieldPanel("intro"),
        FieldPanel("icon_stats"),
        MultiFieldPanel([FieldPanel("achievements_heading"), FieldPanel("achievements")], heading="Achievements"),
        FieldPanel("focus_heading"),
        InlinePanel("focus_areas", label="Area of focus (tab)", max_num=6),
        FieldPanel("featured_resources"),
        FieldPanel("featured_story"),
        FieldPanel("body"),
        MultiFieldPanel([FieldPanel("donate_heading"), FieldPanel("appeal_code")], heading="Donate box"),
    ]
    search_fields = BasePage.search_fields + [index.SearchField("intro"), index.SearchField("short_description")]
    parent_page_types = ["core.FolderPage", "pages.StandardPage"]
    subpage_types = ["pages.StandardPage"]

    class Meta:
        verbose_name = "Program page"

    def get_context(self, request, *args, **kwargs):
        from apps.resources.models import Resource
        from apps.stories.models import StoryPage

        ctx = super().get_context(request, *args, **kwargs)
        ctx["related_stories"] = (
            StoryPage.objects.live().public().filter(programs=self).order_by("-date")[:3]
        )
        ctx["resources"] = Resource.objects.filter(programs=self).order_by("-date")[:12]
        return ctx


class FocusArea(Orderable):
    page = ParentalKey(ProgramPage, on_delete=models.CASCADE, related_name="focus_areas")
    title = models.CharField(max_length=120)
    overview = RichTextField(features=["bold", "italic", "link", "ul"])
    read_more_page = models.ForeignKey(
        "wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    key_stats = StreamField([("stat", IconStatBlock())], blank=True, use_json_field=True, max_num=3)

    panels = [FieldPanel("title"), FieldPanel("overview"), FieldPanel("read_more_page"), FieldPanel("key_stats")]
