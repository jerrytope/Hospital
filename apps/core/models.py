from django.db import models
from django.shortcuts import redirect
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel, TabbedInterface, ObjectList
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.images.models import AbstractImage, AbstractRendition, Image
from wagtail.models import Page

from .blocks import FooterColumnBlock, MegaMenuItemBlock, MenuSubLinkBlock


# --- Images -----------------------------------------------------------------


class CustomImage(AbstractImage):
    """Image library entry with the credit and consent fields the charity needs."""

    alt_text = models.CharField(
        max_length=255, blank=True, help_text="Describe the image for screen readers. Required for publishing."
    )
    credit = models.CharField(max_length=255, blank=True, help_text="Photographer / copyright holder")
    consent_obtained = models.BooleanField(
        default=False, help_text="Tick when everyone identifiable in the photo has given consent"
    )

    admin_form_fields = Image.admin_form_fields + ("alt_text", "credit", "consent_obtained")

    @property
    def default_alt_text(self):
        return self.alt_text or self.title


class CustomRendition(AbstractRendition):
    image = models.ForeignKey(CustomImage, on_delete=models.CASCADE, related_name="renditions")

    class Meta:
        unique_together = (("image", "filter_spec", "focal_point_key"),)


# --- Site settings (editable by the owner in Admin → Settings) -------------


@register_setting(icon="cog")
class OrganisationSettings(BaseGenericSetting):
    name = models.CharField(max_length=120, default="Haven Medical Relief")
    tagline = models.CharField(max_length=200, blank=True, default="Care that reaches every corner.")
    logo = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    logo_on_dark = models.ForeignKey(
        "core.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Optional white version of the logo for the dark footer",
    )
    default_share_image = models.ForeignKey(
        "core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Contact
    hq_address = models.TextField(blank=True)
    main_phone = models.CharField(max_length=40, blank=True)
    fax = models.CharField(max_length=40, blank=True)
    general_email = models.EmailField(blank=True)
    donation_hotline = models.CharField(max_length=40, blank=True)
    donations_email = models.EmailField(blank=True)
    media_email = models.EmailField(blank=True)

    # Social
    facebook_url = models.URLField(blank=True)
    x_url = models.URLField("X (Twitter) URL", blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)

    # Legal / footer
    tax_status_text = models.TextField(
        blank=True,
        default="Haven Medical Relief is a registered non-profit organisation. Donations are tax-deductible "
        "to the extent allowed by law.",
    )
    tax_id = models.CharField(max_length=60, blank=True)
    licence_note = models.CharField(max_length=255, blank=True)
    footer_donate_heading = models.CharField(max_length=120, default="Donate Today")
    footer_donate_text = models.TextField(
        blank=True, default="Your gift delivers emergency medical care to families who need it most."
    )

    # Newsletter / cookies
    newsletter_heading = models.CharField(max_length=120, default="Stay up to speed")
    newsletter_text = models.TextField(blank=True, default="Get field updates, emergency alerts and stories of hope.")
    newsletter_consent_text = RichTextField(
        features=["bold", "italic", "link"],
        blank=True,
        default="<p>By submitting this form you agree to receive emails from us. You can unsubscribe at any "
        "time. See our privacy policy.</p>",
    )
    cookie_banner_text = models.TextField(
        default="We use cookies to understand how our site is used and to improve your experience."
    )

    # Analytics (loaded only after cookie consent)
    ga4_measurement_id = models.CharField("GA4 measurement ID", max_length=40, blank=True)
    facebook_pixel_id = models.CharField(max_length=40, blank=True)

    # Sitewide alert banner
    alert_enabled = models.BooleanField(default=False)
    alert_text = models.CharField(max_length=200, blank=True)
    alert_link = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    # Pages referenced from the site chrome
    privacy_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cookie_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    terms_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    fraud_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    faq_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    stories_page = models.ForeignKey(
        "wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="The Stories and News listing page (used for filtered 'Explore more' links)",
    )
    emergencies_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    where_we_work_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    mail_donation_form = models.ForeignKey(
        "wagtaildocs.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="PDF form for donating by post",
    )

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("name"),
                    FieldPanel("tagline"),
                    FieldRowPanel([FieldPanel("logo"), FieldPanel("logo_on_dark")]),
                    FieldPanel("default_share_image"),
                ],
                heading="Organisation",
            ),
            ObjectList(
                [
                    FieldPanel("hq_address"),
                    FieldRowPanel([FieldPanel("main_phone"), FieldPanel("fax")]),
                    FieldRowPanel([FieldPanel("general_email"), FieldPanel("media_email")]),
                    FieldRowPanel([FieldPanel("donation_hotline"), FieldPanel("donations_email")]),
                    FieldPanel("mail_donation_form"),
                ],
                heading="Contact",
            ),
            ObjectList(
                [
                    FieldPanel("facebook_url"),
                    FieldPanel("x_url"),
                    FieldPanel("instagram_url"),
                    FieldPanel("linkedin_url"),
                    FieldPanel("youtube_url"),
                ],
                heading="Social",
            ),
            ObjectList(
                [
                    FieldPanel("footer_donate_heading"),
                    FieldPanel("footer_donate_text"),
                    FieldPanel("tax_status_text"),
                    FieldPanel("tax_id"),
                    FieldPanel("licence_note"),
                    FieldPanel("newsletter_heading"),
                    FieldPanel("newsletter_text"),
                    FieldPanel("newsletter_consent_text"),
                    FieldPanel("cookie_banner_text"),
                ],
                heading="Footer & forms",
            ),
            ObjectList(
                [
                    MultiFieldPanel(
                        [FieldPanel("alert_enabled"), FieldPanel("alert_text"), FieldPanel("alert_link")],
                        heading="Sitewide alert banner",
                    ),
                    FieldPanel("privacy_page"),
                    FieldPanel("cookie_page"),
                    FieldPanel("terms_page"),
                    FieldPanel("fraud_page"),
                    FieldPanel("faq_page"),
                    FieldPanel("stories_page"),
                    FieldPanel("emergencies_page"),
                    FieldPanel("where_we_work_page"),
                ],
                heading="Key pages & alert",
            ),
            ObjectList(
                [FieldPanel("ga4_measurement_id"), FieldPanel("facebook_pixel_id")],
                heading="Analytics",
            ),
        ]
    )

    class Meta:
        verbose_name = "Organisation settings"


@register_setting(icon="list-ul")
class NavigationSettings(BaseGenericSetting):
    header_menu = StreamField([("item", MegaMenuItemBlock())], blank=True, use_json_field=True)
    footer_columns = StreamField([("column", FooterColumnBlock())], blank=True, use_json_field=True)
    legal_links = StreamField([("link", MenuSubLinkBlock())], blank=True, use_json_field=True)

    panels = [FieldPanel("header_menu"), FieldPanel("footer_columns"), FieldPanel("legal_links")]

    class Meta:
        verbose_name = "Menus"


# --- Page base classes -----------------------------------------------------------


class BasePage(Page):
    """Fields shared by every content page: the hero and share image."""

    eyebrow = models.CharField(max_length=60, blank=True, help_text="Small label above the title, e.g. 'Our Work'")
    hero_image = models.ForeignKey("core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    hero_heading = models.CharField(max_length=200, blank=True, help_text="Defaults to the page title")
    hero_intro = models.TextField(blank=True, help_text="One or two sentences under the title")
    share_image = models.ForeignKey(
        "core.CustomImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Image used when shared on social media (defaults to the hero image)",
    )
    show_section_badges = models.BooleanField(
        default=True, help_text="Show quick-link badges to sibling pages above the footer"
    )

    hero_panels = [
        MultiFieldPanel(
            [FieldPanel("eyebrow"), FieldPanel("hero_heading"), FieldPanel("hero_intro"), FieldPanel("hero_image")],
            heading="Hero",
        )
    ]
    promote_panels = Page.promote_panels + [FieldPanel("share_image"), FieldPanel("show_section_badges")]

    class Meta:
        abstract = True

    @property
    def display_heading(self):
        return self.hero_heading or self.title

    def get_share_image(self):
        return self.share_image or self.hero_image

    def get_section_badges(self):
        if not self.show_section_badges:
            return []
        # A section hub (child of the homepage) shows its own children; deeper pages show
        # their section hub and its children.
        hub = self if self.depth <= 3 else self.get_ancestors().filter(depth=3).first()
        if not hub:
            return []
        children = list(hub.get_children().live().public().in_menu())
        return [hub] + children if children else []


class FolderPage(Page):
    """URL container such as /program/ or /story/. Visiting it redirects to a chosen page."""

    redirect_to = models.ForeignKey(
        "wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Where visitors go if they open this folder's URL directly",
    )

    content_panels = Page.content_panels + [FieldPanel("redirect_to")]

    class Meta:
        verbose_name = "URL folder"

    def serve(self, request, *args, **kwargs):
        if self.redirect_to:
            return redirect(self.redirect_to.url)
        return redirect("/")
