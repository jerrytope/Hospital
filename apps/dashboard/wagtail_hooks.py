from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.admin.ui.components import Component
from wagtail.snippets.models import register_snippet

from apps.core.templatetags.site_tags import MENU_CACHE_KEY

from . import views
from .viewsets import (
    ContentLibraryGroup,
    InvolvementGroup,
    appeal_viewset,
    bank_account_viewset,
    donation_viewset,
    ecard_viewset,
    gift_item_viewset,
    gift_order_viewset,
    recurring_viewset,
    report_queue_viewset,
    subscriber_viewset,
    webhook_viewset,
)

# --- Snippets ------------------------------------------------------------------------------

register_snippet(ContentLibraryGroup)
register_snippet(InvolvementGroup)
register_snippet(bank_account_viewset)
register_snippet(appeal_viewset)
register_snippet(gift_item_viewset)


@hooks.register("register_admin_viewset")
def register_giving_viewsets():
    return [
        donation_viewset,
        recurring_viewset,
        gift_order_viewset,
        subscriber_viewset,
        webhook_viewset,
        report_queue_viewset,
        ecard_viewset,
    ]


# --- Custom admin pages ------------------------------------------------------------------------


@hooks.register("register_admin_urls")
def register_dashboard_urls():
    return [
        path("giving/", views.giving_overview, name="dashboard_giving"),
        path("giving/appeals-report/", views.appeals_report, name="dashboard_appeals_report"),
        path("bank-transfers/", views.bank_transfers, name="dashboard_bank_transfers"),
        path("bank-transfers/<int:pk>/", views.bank_transfer_action, name="dashboard_bank_transfer_action"),
        path("fundraisers/", views.fundraisers, name="dashboard_fundraisers"),
        path("fundraisers/<int:pk>/", views.fundraiser_action, name="dashboard_fundraiser_action"),
        path("donation-action/<int:pk>/", views.donation_action, name="dashboard_donation_action"),
        path("monthly-action/<int:pk>/", views.recurring_action, name="dashboard_recurring_action"),
        path("webhook-retry/<int:pk>/", views.webhook_retry, name="dashboard_webhook_retry"),
    ]


class PermMenuItem(MenuItem):
    def __init__(self, *args, perm=None, **kwargs):
        self.perm = perm
        super().__init__(*args, **kwargs)

    def is_shown(self, request):
        return not self.perm or request.user.has_perm(self.perm)


class CountMenuItem(PermMenuItem):
    """Shows a live count in the label, e.g. 'Bank transfer queue (3)'."""

    def __init__(self, *args, count_fn=None, **kwargs):
        self.count_fn = count_fn
        super().__init__(*args, **kwargs)

    def render_component(self, request):
        component = super().render_component(request)
        n = self.count_fn() if self.count_fn else 0
        if n:
            component.label = f"{self.label} ({n})"
        return component


def _viewset_url(viewset):
    return reverse(viewset.get_url_name("index"))


@hooks.register("register_admin_menu_item")
def giving_menu():
    from apps.fundraising.models import Fundraiser
    from apps.giving.models import BankTransferNotice

    items = [
        PermMenuItem("Giving overview", reverse("dashboard_giving"), icon_name="view", order=10, perm="giving.view_donation"),
        PermMenuItem("Donations", _viewset_url(donation_viewset), icon_name="pick", order=20, perm="giving.view_donation"),
        PermMenuItem("Monthly gifts", _viewset_url(recurring_viewset), icon_name="repeat", order=30, perm="giving.view_recurringgift"),
        CountMenuItem(
            "Bank transfer queue",
            reverse("dashboard_bank_transfers"),
            icon_name="tasks",
            order=40,
            perm="giving.view_banktransfernotice",
            count_fn=lambda: BankTransferNotice.objects.filter(status="pending").count(),
        ),
        PermMenuItem("Bank accounts (shown on site)", reverse(bank_account_viewset.get_url_name("list")), icon_name="site", order=50, perm="giving.change_bankaccount"),
        PermMenuItem("Appeal codes", reverse(appeal_viewset.get_url_name("list")), icon_name="tag", order=60, perm="giving.change_appeal"),
        PermMenuItem("Appeals report", reverse("dashboard_appeals_report"), icon_name="table", order=70, perm="giving.view_donation"),
        PermMenuItem("Gift catalogue items", reverse(gift_item_viewset.get_url_name("list")), icon_name="pick", order=80, perm="giving.change_giftitem"),
        PermMenuItem("Gift orders", _viewset_url(gift_order_viewset), icon_name="pick", order=90, perm="giving.view_giftorder"),
        PermMenuItem("E-cards", _viewset_url(ecard_viewset), icon_name="mail", order=100, perm="giving.view_ecard"),
        CountMenuItem(
            "Fundraisers (moderation)",
            reverse("dashboard_fundraisers"),
            icon_name="group",
            order=110,
            perm="fundraising.change_fundraiser",
            count_fn=lambda: Fundraiser.objects.filter(status="pending").count(),
        ),
        PermMenuItem("Fundraiser reports", _viewset_url(report_queue_viewset), icon_name="warning", order=120, perm="fundraising.view_fundraiserreport"),
        PermMenuItem("Newsletter subscribers", _viewset_url(subscriber_viewset), icon_name="mail", order=130, perm="newsletter.view_subscriber"),
        PermMenuItem("Payment webhook log", _viewset_url(webhook_viewset), icon_name="code", order=140, perm="payments.view_webhookevent"),
    ]
    return SubmenuMenuItem("Giving", Menu(items=items), icon_name="pick", order=150)


# --- Admin home panel ----------------------------------------------------------------------------


class GivingPanel(Component):
    name = "giving_summary"
    template_name = "dashboard/home_panel.html"
    order = 50

    def __init__(self, request):
        self.request = request

    def get_context_data(self, parent_context=None):
        from .views import overview_stats

        return {"stats": overview_stats(self.request.user), "request": self.request}


@hooks.register("construct_homepage_panels")
def add_giving_panel(request, panels):
    if request.user.has_perm("giving.view_donation"):
        panels.insert(0, GivingPanel(request))


# --- Bank detail change alerts --------------------------------------------------------------------


def _bank_alert(request, instance, action):
    from apps.giving.models import BankAccount
    from apps.giving.tasks import notify_bank_details_changed

    if isinstance(instance, BankAccount):
        notify_bank_details_changed.delay(str(instance), action, getattr(request.user, "email", "unknown"))


@hooks.register("after_create_snippet")
def bank_created(request, instance):
    _bank_alert(request, instance, "added")


@hooks.register("after_edit_snippet")
def bank_edited(request, instance):
    _bank_alert(request, instance, "changed")


@hooks.register("after_delete_snippet")
def bank_deleted(request, instances):
    for instance in instances:
        _bank_alert(request, instance, "deleted")


# --- Keep the cached header menu fresh ------------------------------------------------------------


def _clear_menu_cache(*args, **kwargs):
    cache.delete(MENU_CACHE_KEY)


for hook_name in ("after_publish_page", "after_unpublish_page", "after_move_page", "after_delete_page"):
    hooks.register(hook_name, _clear_menu_cache)


@receiver(post_save)
@receiver(post_delete)
def clear_menu_on_related_change(sender, **kwargs):
    from apps.core.models import NavigationSettings
    from apps.taxonomy.models import Region

    if sender in (NavigationSettings, Region):
        _clear_menu_cache()
