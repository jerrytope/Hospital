from urllib.parse import urlencode

from django import template
from django.core.cache import cache
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core.blocks import link_href, link_text

register = template.Library()

MENU_CACHE_KEY = "site-header-menu-v1"


@register.simple_tag
def icon(name, css_class="w-6 h-6", label=""):
    """Inline SVG icon from the sprite in includes/icon_sprite.html."""
    if not name:
        return ""
    aria = format_html('role="img" aria-label="{}"', label) if label else mark_safe('aria-hidden="true"')
    return format_html(
        '<svg class="icon {}" {} focusable="false"><use href="#i-{}"></use></svg>', css_class, aria, name
    )


@register.filter
def money(amount, currency="NGN"):
    from apps.giving.models import money as fmt

    return fmt(amount, currency)


@register.filter
def href(link_value):
    return link_href(link_value)


@register.filter
def linktext(link_value, fallback="Learn more"):
    return link_text(link_value, fallback)


@register.simple_tag
def menu_href(item):
    """URL for a menu / promo-card struct value with page and url keys."""
    page = item.get("page")
    if page:
        return page.url
    return item.get("url") or "#"


@register.simple_tag
def donate_href(appeal="", emergency=None, fundraiser=None, frequency=""):
    params = {}
    if appeal:
        params["appeal"] = appeal
    if emergency:
        params["emergency"] = getattr(emergency, "pk", emergency)
    if fundraiser:
        params["fundraiser"] = getattr(fundraiser, "slug", fundraiser)
    if frequency:
        params["frequency"] = frequency
    query = urlencode(params)
    return "/donate/" + (f"?{query}" if query else "")


@register.simple_tag(takes_context=True)
def stories_url(context, **filters):
    """Link to Stories and News pre-filtered, e.g. {% stories_url program=page.slug %}."""
    settings_obj = _org_settings(context)
    page = settings_obj.stories_page if settings_obj else None
    base = page.url if page else "/stories-and-news/"
    clean = {k: v for k, v in filters.items() if v}
    return base + (f"?{urlencode(clean)}" if clean else "")


def _org_settings(context):
    from apps.core.models import OrganisationSettings

    request = context.get("request")
    return OrganisationSettings.load(request_or_site=request) if request else OrganisationSettings.load()


@register.simple_tag
def header_menu():
    """Header mega menu with its automatic panels filled in. Cached; cleared on publish."""
    data = cache.get(MENU_CACHE_KEY)
    if data is not None:
        return data
    from apps.core.models import NavigationSettings
    from apps.countries.models import CountryPage
    from apps.emergencies.models import EmergencyPage
    from apps.stories.models import StoryPage
    from apps.taxonomy.models import Region

    nav = NavigationSettings.load()
    items = []
    for block in nav.header_menu:
        value = block.value
        item = {
            "label": value["label"],
            "href": value["page"].url if value.get("page") else "#",
            "left_links": [
                {
                    "label": link["label"],
                    "href": link["page"].url if link.get("page") else (link.get("url") or "#"),
                    "children": [
                        {"label": c["label"], "href": c["page"].url if c.get("page") else (c.get("url") or "#")}
                        for c in (link.get("children") or [])
                    ],
                }
                for link in value.get("left_links") or []
            ],
            "panel": value.get("panel") or "cards",
            "cards": [],
        }
        if item["panel"] == "cards":
            for card in value.get("promo_cards") or []:
                item["cards"].append(
                    {
                        "title": card["title"],
                        "text": card.get("text") or "",
                        "href": card["page"].url if card.get("page") else (card.get("url") or "#"),
                        "button": card.get("button_label") or "Learn more",
                        "image": card.get("image"),
                    }
                )
        elif item["panel"] == "emergencies":
            for e in EmergencyPage.objects.live().public().filter(status="active").order_by("-featured", "-year_start")[:3]:
                item["cards"].append(
                    {"title": e.title, "text": e.card_summary, "href": e.url, "button": "Read more", "image": e.hero_image}
                )
        elif item["panel"] == "stories":
            for s in StoryPage.objects.live().public().order_by("-date")[:4]:
                item["cards"].append(
                    {"title": s.title, "text": s.excerpt, "href": s.url, "button": "Read more", "image": None}
                )
        elif item["panel"] == "regions":
            countries = CountryPage.objects.live().public().filter(status="current", has_detail_page=True).order_by("title")
            regions = []
            for region in Region.objects.all():
                regions.append(
                    {
                        "name": region.name,
                        "slug": region.slug,
                        "countries": [{"name": c.title, "href": c.url} for c in countries if c.region_id == region.pk],
                    }
                )
            item["regions"] = [r for r in regions if r["countries"]]
        items.append(item)
    cache.set(MENU_CACHE_KEY, items, 60 * 30)
    return items


@register.simple_tag
def footer_navigation():
    from apps.core.models import NavigationSettings

    nav = NavigationSettings.load()
    columns = []
    for block in nav.footer_columns:
        columns.append(
            {
                "heading": block.value["heading"],
                "links": [
                    {"label": link["label"], "href": link["page"].url if link.get("page") else (link.get("url") or "#")}
                    for link in block.value["links"]
                ],
            }
        )
    legal = [
        {"label": b.value["label"], "href": b.value["page"].url if b.value.get("page") else (b.value.get("url") or "#")}
        for b in nav.legal_links
    ]
    return {"columns": columns, "legal": legal}


@register.simple_tag
def bank_accounts(where="donate", currency=None, emergency=None):
    from apps.giving.models import BankAccount

    qs = BankAccount.objects.filter(active=True)
    if where == "donate":
        qs = qs.filter(show_on_donate=True)
    elif where == "contact":
        qs = qs.filter(show_on_contact=True)
    elif where == "footer":
        qs = qs.filter(show_in_footer=True)
    if currency:
        qs = qs.filter(currency=currency)
    if emergency:
        dedicated = qs.filter(emergency=emergency)
        if dedicated.exists():
            return dedicated
    return qs.filter(emergency__isnull=True) if emergency is not None else qs


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def slugify_id(value):
    from django.utils.text import slugify

    return slugify(value)


@register.filter
def as_list(value):
    return [value]


@register.simple_tag(takes_context=True)
def seo(context):
    """Title, description, share image and canonical URL for the current page or view."""
    from django.utils.html import strip_tags

    from apps.core.models import OrganisationSettings

    request = context.get("request")
    org = OrganisationSettings.load(request_or_site=request) if request else OrganisationSettings.load()
    page = context.get("page")
    data = {"title": org.name, "description": org.tagline, "image": org.default_share_image, "url": "", "article": False}
    if page is not None and hasattr(page, "full_url"):
        data["title"] = getattr(page, "seo_title", "") or page.title
        data["description"] = (
            getattr(page, "search_description", "") or getattr(page, "dek", "") or getattr(page, "hero_intro", "") or org.tagline
        )
        image = page.get_share_image() if hasattr(page, "get_share_image") else None
        data["image"] = image or org.default_share_image
        data["url"] = page.full_url or ""
        data["article"] = bool(getattr(page, "story_type", ""))
        data["date"] = getattr(page, "date", None)
        data["author"] = getattr(page, "author", "")
    data["description"] = strip_tags(data["description"] or "")
    return data
