from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.search import index

from apps.core.blocks import story_body_blocks
from apps.core.models import BasePage

STORY_TYPES = [
    ("story", "Story"),
    ("update", "Update / Alert"),
    ("video", "Video"),
    ("press", "Press Release"),
    ("supporter", "Supporter Profile"),
]


class StoryPage(BasePage):
    """Story, update/alert, video, press release or supporter profile (one template)."""

    story_type = models.CharField(max_length=12, choices=STORY_TYPES, default="story")
    dek = models.CharField("Summary line (dek)", max_length=300, blank=True)
    date = models.DateField(default=timezone.localdate)
    author = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=120, blank=True, help_text="Shown in the meta line, e.g. 'Maiduguri, Nigeria'")
    photo_credit = models.CharField(max_length=200, blank=True)
    video_url = models.URLField(blank=True, help_text="For video posts: YouTube or Vimeo link")
    featured = models.BooleanField(default=False, help_text="Feature at the top of Stories and News")
    highlighted = models.BooleanField(default=False, help_text="Show in the three highlighted cards")
    body = StreamField(story_body_blocks(), blank=True, use_json_field=True)
    appeal_code = models.CharField(max_length=40, blank=True)

    programs = ParentalManyToManyField("programs.ProgramPage", blank=True, related_name="stories")
    countries = ParentalManyToManyField("countries.CountryPage", blank=True, related_name="stories")
    emergencies = ParentalManyToManyField("emergencies.EmergencyPage", blank=True, related_name="stories")
    topics = ParentalManyToManyField("taxonomy.Topic", blank=True, related_name="stories")

    content_panels = BasePage.content_panels + [
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("story_type"), FieldPanel("date")]),
                FieldPanel("dek"),
                FieldPanel("hero_image"),
                FieldRowPanel([FieldPanel("author"), FieldPanel("location")]),
                FieldPanel("photo_credit"),
                FieldPanel("video_url"),
                FieldRowPanel([FieldPanel("featured"), FieldPanel("highlighted")]),
            ],
            heading="Story details",
        ),
        FieldPanel("body"),
        MultiFieldPanel(
            [FieldPanel("programs"), FieldPanel("countries"), FieldPanel("emergencies"), FieldPanel("topics")],
            heading="Tags (power filters and 'Read more' blocks)",
        ),
        FieldPanel("appeal_code"),
    ]
    search_fields = BasePage.search_fields + [
        index.SearchField("dek"),
        index.SearchField("body"),
        index.FilterField("story_type"),
        index.FilterField("date"),
    ]
    parent_page_types = ["core.FolderPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Story / news item"
        ordering = ["-date"]

    @property
    def type_label(self):
        return dict(STORY_TYPES).get(self.story_type, "Story")

    @property
    def excerpt(self):
        if self.dek:
            return self.dek
        if self.search_description:
            return self.search_description
        for block in self.body:
            if block.block_type == "rich_text":
                from django.utils.html import strip_tags

                text = strip_tags(str(block.value))
                return (text[:220] + "…") if len(text) > 220 else text
        return ""

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        related = StoryPage.objects.live().public().exclude(pk=self.pk)
        tag_q = models.Q(programs__in=self.programs.all()) | models.Q(countries__in=self.countries.all()) | models.Q(
            emergencies__in=self.emergencies.all()
        ) | models.Q(topics__in=self.topics.all())
        ctx["related_stories"] = related.filter(tag_q).distinct().order_by("-date")[:3] or related.order_by("-date")[:3]
        return ctx


class StoriesIndexPage(BasePage):
    """/stories-and-news/ — featured story, highlights, faceted filters, paginated results."""

    per_page = models.PositiveIntegerField(default=12)

    content_panels = BasePage.content_panels + BasePage.hero_panels + [FieldPanel("per_page")]
    max_count = 1
    subpage_types = ["pages.StandardPage"]

    class Meta:
        verbose_name = "Stories and News page"

    def get_context(self, request, *args, **kwargs):
        from .filters import StoryFilter

        ctx = super().get_context(request, *args, **kwargs)
        base = StoryPage.objects.live().public().order_by("-date", "-first_published_at")
        story_filter = StoryFilter(request.GET, queryset=base)
        filtered = story_filter.qs.distinct()
        is_filtered = any(val for key, vals in request.GET.lists() if key != "page" for val in vals)

        featured = None
        highlighted = []
        if not is_filtered:
            featured = base.filter(featured=True).first() or base.first()
            highlighted = list(base.filter(highlighted=True).exclude(pk=getattr(featured, "pk", None))[:3])

        paginator = Paginator(filtered, self.per_page)
        try:
            page_obj = paginator.page(request.GET.get("page") or 1)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        query = request.GET.copy()
        query.pop("page", None)
        ctx.update(
            {
                "filter": story_filter,
                "featured_story": featured,
                "highlighted_stories": highlighted,
                "page_obj": page_obj,
                "results": page_obj.object_list,
                "is_filtered": is_filtered,
                "querystring": query.urlencode(),
                "page_range": paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1),
            }
        )
        return ctx

    def get_template(self, request, *args, **kwargs):
        if getattr(request, "htmx", False) or request.headers.get("HX-Request"):
            return "stories/partials/results.html"
        return super().get_template(request, *args, **kwargs)
