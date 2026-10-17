"""StreamField block library shared by every page type.

Editors build pages from these blocks. Each block renders with the template in
templates/blocks/<name>.html.
"""
from django.core.exceptions import ValidationError
from wagtail import blocks
from wagtail.contrib.table_block.blocks import TableBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock

from .icons import ICON_CHOICES

RICH_FEATURES = ["h2", "h3", "h4", "bold", "italic", "link", "document-link", "ol", "ul", "hr", "blockquote"]
SIMPLE_FEATURES = ["bold", "italic", "link"]


class LinkBlock(blocks.StructBlock):
    """A link to either an internal page or an external URL."""

    label = blocks.CharBlock(required=False)
    page = blocks.PageChooserBlock(required=False)
    url = blocks.CharBlock(required=False, help_text="External URL or path, used if no page is chosen")

    class Meta:
        icon = "link"
        form_classname = "struct-block link-block"

    def clean(self, value):
        value = super().clean(value)
        if not value.get("page") and not value.get("url"):
            raise blocks.StructBlockValidationError(
                block_errors={"url": ValidationError("Choose a page or enter a URL")}
            )
        return value


def link_href(value):
    if not value:
        return ""
    page = value.get("page")
    if page:
        return page.url
    return value.get("url") or ""


def link_text(value, fallback="Learn more"):
    if not value:
        return fallback
    if value.get("label"):
        return value["label"]
    if value.get("page"):
        return value["page"].title
    return fallback


class OptionalLinkBlock(LinkBlock):
    def clean(self, value):
        return blocks.StructBlock.clean(self, value)


# --- Content blocks ---------------------------------------------------------


class HeadingBlock(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False)
    heading = blocks.CharBlock()
    intro = blocks.TextBlock(required=False)
    anchor = blocks.CharBlock(required=False, help_text="Optional id for in-page links, e.g. 'history'")

    class Meta:
        icon = "title"
        template = "blocks/heading.html"


class RichTextSectionBlock(blocks.RichTextBlock):
    def __init__(self, **kwargs):
        super().__init__(features=RICH_FEATURES, **kwargs)

    class Meta:
        icon = "pilcrow"
        template = "blocks/rich_text.html"


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption = blocks.CharBlock(required=False)
    full_width = blocks.BooleanBlock(required=False)

    class Meta:
        icon = "image"
        template = "blocks/image.html"


class QuoteBlock(blocks.StructBlock):
    quote = blocks.TextBlock()
    name = blocks.CharBlock(required=False)
    role = blocks.CharBlock(required=False)
    image = ImageChooserBlock(required=False)

    class Meta:
        icon = "openquote"
        template = "blocks/quote.html"


class VideoBlock(blocks.StructBlock):
    video = EmbedBlock(help_text="YouTube or Vimeo URL")
    caption = blocks.CharBlock(required=False)

    class Meta:
        icon = "media"
        template = "blocks/video.html"


class IconStatBlock(blocks.StructBlock):
    icon = blocks.ChoiceBlock(choices=ICON_CHOICES, default="heart-pulse")
    value = blocks.CharBlock(required=False, help_text="e.g. 15.6 million")
    text = blocks.TextBlock()


class IconStatsBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    items = blocks.ListBlock(IconStatBlock(), min_num=1, max_num=6)

    class Meta:
        icon = "pick"
        template = "blocks/icon_stats.html"


class CounterItemBlock(blocks.StructBlock):
    value = blocks.CharBlock(help_text="e.g. 120,000+")
    label = blocks.CharBlock()


class CountersBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    items = blocks.ListBlock(CounterItemBlock(), min_num=1, max_num=6)

    class Meta:
        icon = "order"
        template = "blocks/counters.html"


class AlternatingRowBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    headline = blocks.CharBlock()
    text = blocks.RichTextBlock(features=SIMPLE_FEATURES)
    link = OptionalLinkBlock(required=False)


class AlternatingRowsBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    rows = blocks.ListBlock(AlternatingRowBlock())

    class Meta:
        icon = "doc-full"
        template = "blocks/alternating_rows.html"


class TabBlock(blocks.StructBlock):
    title = blocks.CharBlock()
    body = blocks.RichTextBlock(features=RICH_FEATURES)
    image = ImageChooserBlock(required=False)
    link = OptionalLinkBlock(required=False)


class TabsBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    tabs = blocks.ListBlock(TabBlock(), min_num=1, max_num=8)

    class Meta:
        icon = "list-ul"
        template = "blocks/tabs.html"


class AccordionItemBlock(blocks.StructBlock):
    question = blocks.CharBlock()
    answer = blocks.RichTextBlock(features=RICH_FEATURES)


class AccordionBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    items = blocks.ListBlock(AccordionItemBlock())

    class Meta:
        icon = "help"
        template = "blocks/accordion.html"


class CardBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    label = blocks.CharBlock(required=False)
    title = blocks.CharBlock()
    text = blocks.TextBlock(required=False)
    link = OptionalLinkBlock(required=False)


class CardGridBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    intro = blocks.TextBlock(required=False)
    cards = blocks.ListBlock(CardBlock())

    class Meta:
        icon = "table"
        template = "blocks/card_grid.html"


class LinkCardsBlock(blocks.StructBlock):
    cards = blocks.ListBlock(CardBlock(), min_num=1, max_num=3)

    class Meta:
        icon = "link"
        template = "blocks/link_cards.html"


class IconPointBlock(blocks.StructBlock):
    icon = blocks.ChoiceBlock(choices=ICON_CHOICES, default="heart")
    title = blocks.CharBlock()
    text = blocks.TextBlock(required=False)


class IconPointsBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    items = blocks.ListBlock(IconPointBlock())

    class Meta:
        icon = "list-ul"
        template = "blocks/icon_points.html"


class DocumentItemBlock(blocks.StructBlock):
    title = blocks.CharBlock()
    date = blocks.DateBlock(required=False)
    document = DocumentChooserBlock(required=False)
    url = blocks.URLBlock(required=False)


class DocumentListBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    items = blocks.ListBlock(DocumentItemBlock())

    class Meta:
        icon = "doc-full-inverse"
        template = "blocks/document_list.html"


class DonateBoxBlock(blocks.StructBlock):
    heading = blocks.CharBlock(default="Your gift can save lives")
    text = blocks.TextBlock(required=False)
    button_label = blocks.CharBlock(default="Donate now")
    appeal_code = blocks.CharBlock(required=False, help_text="Tracks donations from this box")

    class Meta:
        icon = "pick"
        template = "blocks/donate_box.html"


class CTABandBlock(blocks.StructBlock):
    heading = blocks.CharBlock()
    text = blocks.TextBlock(required=False)
    link = LinkBlock()
    image = ImageChooserBlock(required=False)

    class Meta:
        icon = "pick"
        template = "blocks/cta_band.html"


class NewsletterBlock(blocks.StructBlock):
    heading = blocks.CharBlock(default="Join our community")
    text = blocks.TextBlock(required=False)

    class Meta:
        icon = "mail"
        template = "blocks/newsletter.html"


class SectionLinksBlock(blocks.StructBlock):
    """Several short sections (heading, paragraph, button), e.g. on Get Involved."""

    heading = blocks.CharBlock(required=False)
    items = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("icon", blocks.ChoiceBlock(choices=ICON_CHOICES, required=False)),
                ("title", blocks.CharBlock()),
                ("text", blocks.TextBlock(required=False)),
                ("link", LinkBlock()),
            ]
        )
    )

    class Meta:
        icon = "list-ul"
        template = "blocks/section_links.html"


# --- Dynamic blocks (pull live content) -------------------------------------


class LatestStoriesBlock(blocks.StructBlock):
    heading = blocks.CharBlock(default="Stories of Hope")
    count = blocks.IntegerBlock(default=3, min_value=1, max_value=12)
    content_type = blocks.ChoiceBlock(
        required=False,
        choices=[
            ("story", "Stories"),
            ("update", "Updates and alerts"),
            ("video", "Videos"),
            ("press", "Press releases"),
            ("supporter", "Supporter profiles"),
        ],
    )
    program = blocks.PageChooserBlock(required=False, page_type="programs.ProgramPage")
    country = blocks.PageChooserBlock(required=False, page_type="countries.CountryPage")
    emergency = blocks.PageChooserBlock(required=False, page_type="emergencies.EmergencyPage")

    class Meta:
        icon = "doc-full"
        template = "blocks/latest_stories.html"

    def get_context(self, value, parent_context=None):
        from apps.stories.models import StoryPage

        ctx = super().get_context(value, parent_context)
        qs = StoryPage.objects.live().public().order_by("-date", "-first_published_at")
        if value.get("content_type"):
            qs = qs.filter(story_type=value["content_type"])
        for field in ("program", "country", "emergency"):
            if value.get(field):
                qs = qs.filter(**{f"{field}s": value[field]})
        ctx["stories"] = qs[: value.get("count") or 3]
        return ctx


class ActiveEmergenciesBlock(blocks.StructBlock):
    heading = blocks.CharBlock(default="Current emergencies")
    count = blocks.IntegerBlock(default=3, min_value=1, max_value=12)

    class Meta:
        icon = "warning"
        template = "blocks/active_emergencies.html"

    def get_context(self, value, parent_context=None):
        from apps.emergencies.models import EmergencyPage

        ctx = super().get_context(value, parent_context)
        ctx["emergencies"] = EmergencyPage.objects.live().filter(status="active").order_by("-featured", "-year_start")[
            : value.get("count") or 3
        ]
        return ctx


class ChildPagesBlock(blocks.StructBlock):
    """Cards for the children of a page, e.g. the 7 program pages under Our Work."""

    heading = blocks.CharBlock(required=False)
    parent = blocks.PageChooserBlock(required=False, help_text="Leave blank to use this page's children")

    class Meta:
        icon = "folder-open-inverse"
        template = "blocks/child_pages.html"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        parent = value.get("parent") or (parent_context or {}).get("page")
        ctx["children"] = parent.get_children().live().public().in_menu().specific() if parent else []
        if parent and not ctx["children"]:
            ctx["children"] = parent.get_children().live().public().specific()
        return ctx


class TimelineTeaserBlock(blocks.StructBlock):
    heading = blocks.CharBlock(default="Our Rich History")
    history_page = blocks.PageChooserBlock(page_type="about.HistoryPage")
    count = blocks.IntegerBlock(default=3, min_value=1, max_value=6)

    class Meta:
        icon = "date"
        template = "blocks/timeline_teaser.html"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        page = value.get("history_page")
        ctx["entries"] = page.specific.timeline_entries.filter(featured=True)[: value["count"]] if page else []
        if page and not ctx["entries"]:
            ctx["entries"] = page.specific.timeline_entries.all()[: value["count"]]
        return ctx


class GivingCardsBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False)
    cards = blocks.ListBlock(CardBlock(), max_num=4)

    class Meta:
        icon = "pick"
        template = "blocks/card_grid.html"


class EmbedHTMLBlock(blocks.RawHTMLBlock):
    """Third-party widgets (crypto, stock transfer, event tickets). Super Admin only by convention."""

    class Meta:
        icon = "code"
        template = "blocks/raw_html.html"


def body_blocks():
    """Blocks available in the general page body."""
    return [
        ("heading", HeadingBlock()),
        ("rich_text", RichTextSectionBlock()),
        ("image", ImageBlock()),
        ("quote", QuoteBlock()),
        ("video", VideoBlock()),
        ("icon_stats", IconStatsBlock()),
        ("counters", CountersBlock()),
        ("alternating_rows", AlternatingRowsBlock()),
        ("tabs", TabsBlock()),
        ("accordion", AccordionBlock()),
        ("card_grid", CardGridBlock()),
        ("link_cards", LinkCardsBlock()),
        ("icon_points", IconPointsBlock()),
        ("section_links", SectionLinksBlock()),
        ("documents", DocumentListBlock()),
        ("table", TableBlock(template="blocks/table.html")),
        ("donate_box", DonateBoxBlock()),
        ("cta_band", CTABandBlock()),
        ("newsletter", NewsletterBlock()),
        ("latest_stories", LatestStoriesBlock()),
        ("active_emergencies", ActiveEmergenciesBlock()),
        ("child_pages", ChildPagesBlock()),
        ("timeline_teaser", TimelineTeaserBlock()),
        ("embed_html", EmbedHTMLBlock()),
    ]


def story_body_blocks():
    return [
        ("rich_text", RichTextSectionBlock()),
        ("heading", HeadingBlock()),
        ("image", ImageBlock()),
        ("quote", QuoteBlock()),
        ("video", VideoBlock()),
        ("donate_box", DonateBoxBlock()),
        ("table", TableBlock(template="blocks/table.html")),
        ("embed_html", EmbedHTMLBlock()),
    ]


# --- Navigation blocks --------------------------------------------------------


class MenuSubLinkBlock(blocks.StructBlock):
    label = blocks.CharBlock()
    page = blocks.PageChooserBlock(required=False)
    url = blocks.CharBlock(required=False)


class MenuLinkBlock(blocks.StructBlock):
    label = blocks.CharBlock()
    page = blocks.PageChooserBlock(required=False)
    url = blocks.CharBlock(required=False)
    children = blocks.ListBlock(MenuSubLinkBlock(), required=False, default=[])


class PromoCardBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    title = blocks.CharBlock()
    text = blocks.TextBlock(required=False)
    page = blocks.PageChooserBlock(required=False)
    url = blocks.CharBlock(required=False)
    button_label = blocks.CharBlock(required=False, default="Learn more")


class MegaMenuItemBlock(blocks.StructBlock):
    label = blocks.CharBlock()
    page = blocks.PageChooserBlock(required=False, help_text="Landing page for this menu item")
    left_links = blocks.ListBlock(MenuLinkBlock(), required=False, default=[])
    panel = blocks.ChoiceBlock(
        choices=[
            ("cards", "Promo cards (chosen below)"),
            ("emergencies", "Current emergencies (automatic)"),
            ("stories", "Latest stories (automatic)"),
            ("regions", "Regions and countries (automatic)"),
        ],
        default="cards",
        help_text="What the right side of the dropdown shows",
    )
    promo_cards = blocks.ListBlock(PromoCardBlock(), required=False, default=[], max_num=4)

    class Meta:
        icon = "list-ul"


class FooterColumnBlock(blocks.StructBlock):
    heading = blocks.CharBlock()
    links = blocks.ListBlock(MenuSubLinkBlock())

    class Meta:
        icon = "list-ul"
