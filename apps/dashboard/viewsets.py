"""Admin listings for everything the owner manages that isn't a page.

Snippets (content the site displays) and ModelViewSets (giving records) are grouped into
admin menus. Every listing supports search, filters and CSV/XLSX export.
"""
from wagtail.admin.ui.tables import BooleanColumn, Column, DateColumn
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from apps.about.models import Person, Report
from apps.emergencies.models import MediaAlert, PastEmergency, SituationReport
from apps.fundraising.models import FundraiserReport
from apps.giving.models import Appeal, BankAccount, Donation, ECard, GiftItem, GiftOrder, RecurringGift
from apps.involvement.models import Event, Job, Tender
from apps.newsletter.models import Subscriber
from apps.pages.models import Office
from apps.payments.models import WebhookEvent
from apps.resources.models import Resource
from apps.taxonomy.models import Region, Topic


# --- Content library (snippets) -----------------------------------------------------


class RegionViewSet(SnippetViewSet):
    model = Region
    icon = "site"
    list_display = ["name", "order"]


class TopicViewSet(SnippetViewSet):
    model = Topic
    icon = "tag"
    search_fields = ["name"]


class ResourceViewSet(SnippetViewSet):
    model = Resource
    icon = "doc-full"
    list_display = ["title", "kind", DateColumn("date")]
    list_filter = ["kind", "programs", "countries", "emergencies"]
    search_fields = ["title"]


class SitRepViewSet(SnippetViewSet):
    model = SituationReport
    icon = "doc-full-inverse"
    menu_label = "Situation reports"
    list_display = ["title", "number", DateColumn("date"), "emergency", "country"]
    list_filter = ["emergency", "country"]
    search_fields = ["title"]
    search_backend_name = None


class MediaAlertViewSet(SnippetViewSet):
    model = MediaAlert
    icon = "openquote"
    list_display = ["headline", "outlet", DateColumn("date"), "emergency"]
    list_filter = ["emergency"]
    search_fields = ["headline", "outlet"]
    search_backend_name = None


class PastEmergencyViewSet(SnippetViewSet):
    model = PastEmergency
    icon = "history"
    menu_label = "Past emergencies table"
    list_display = ["country", "name", "year", "order"]
    search_fields = ["country", "name", "year"]
    search_backend_name = None
    list_per_page = 100


class PersonViewSet(SnippetViewSet):
    model = Person
    icon = "user"
    menu_label = "People (leadership)"
    list_display = ["name", "title", "group", "order"]
    list_filter = ["group"]
    search_fields = ["name"]
    list_per_page = 100


class ReportViewSet(SnippetViewSet):
    model = Report
    icon = "doc-full"
    menu_label = "Financial & annual reports"
    list_display = ["title", "report_type", "year"]
    list_filter = ["report_type", "year"]


class OfficeViewSet(SnippetViewSet):
    model = Office
    icon = "home"
    list_display = ["name", "phone", "order"]


class ContentLibraryGroup(SnippetViewSetGroup):
    menu_label = "Content library"
    menu_icon = "folder-open-inverse"
    menu_order = 210
    items = (
        ResourceViewSet,
        SitRepViewSet,
        MediaAlertViewSet,
        PastEmergencyViewSet,
        PersonViewSet,
        ReportViewSet,
        OfficeViewSet,
        RegionViewSet,
        TopicViewSet,
    )


class EventViewSet(SnippetViewSet):
    model = Event
    icon = "date"
    list_display = ["title", DateColumn("start"), "place"]
    search_fields = ["title"]


class TenderViewSet(SnippetViewSet):
    model = Tender
    icon = "doc-full"
    menu_label = "Open tenders"
    list_display = ["title", "reference", "country", DateColumn("deadline"), BooleanColumn("is_open", label="Open")]
    search_fields = ["title"]


class JobViewSet(SnippetViewSet):
    model = Job
    icon = "user"
    list_display = ["title", "location", "job_type", DateColumn("deadline"), BooleanColumn("published")]
    list_filter = ["job_type", "published"]
    search_fields = ["title"]


class InvolvementGroup(SnippetViewSetGroup):
    menu_label = "Events, tenders & jobs"
    menu_icon = "date"
    menu_order = 220
    items = (EventViewSet, TenderViewSet, JobViewSet)


# --- Giving -----------------------------------------------------------------------------


class AmountColumn(Column):
    def get_value(self, instance):
        return instance.display_amount


class BankAccountViewSet(SnippetViewSet):
    model = BankAccount
    icon = "site"
    menu_label = "Bank accounts (shown on site)"
    list_display = ["bank_name", "account_name", "account_number", "currency", "emergency", BooleanColumn("active")]
    list_filter = ["currency", "active"]


class AppealViewSet(SnippetViewSet):
    model = Appeal
    icon = "tag"
    menu_label = "Appeal codes"
    list_display = ["code", "name", "emergency", BooleanColumn("active"), BooleanColumn("auto_created", label="Unregistered")]
    list_filter = ["active", "auto_created"]
    search_fields = ["code", "name"]
    search_backend_name = None


class GiftItemViewSet(SnippetViewSet):
    model = GiftItem
    icon = "pick"
    menu_label = "Gift catalogue items"
    list_display = ["title", "price_ngn", "price_usd", BooleanColumn("active"), "order"]


class DonationViewSet(ModelViewSet):
    model = Donation
    icon = "pick"
    menu_label = "Donations"
    add_to_admin_menu = False
    form_fields = ["admin_notes"]
    list_display = [
        "reference",
        Column("donor_name", label="Donor"),
        "email",
        AmountColumn("amount", label="Amount"),
        "frequency",
        "status",
        "provider",
        "appeal_code",
        DateColumn("created_at", label="Created"),
    ]
    list_filter = ["status", "currency", "frequency", "provider", "appeal", "emergency", "created_at"]
    search_fields = ["reference", "email", "first_name", "last_name", "appeal_code", "provider_reference"]
    search_backend_name = None
    list_per_page = 50
    inspect_view_enabled = True
    inspect_template_name = "dashboard/donation_inspect.html"
    list_export = [
        "reference", "created_at", "paid_at", "first_name", "last_name", "email", "phone", "amount", "currency",
        "frequency", "status", "provider", "provider_reference", "appeal_code", "emergency", "fundraiser", "source_url",
    ]
    export_filename = "donations"


class RecurringGiftViewSet(ModelViewSet):
    model = RecurringGift
    icon = "repeat"
    menu_label = "Monthly gifts"
    add_to_admin_menu = False
    form_fields = ["status"]
    list_display = ["reference", "email", AmountColumn("amount", label="Amount / month"), "provider", "status", "next_charge_date"]
    list_filter = ["status", "currency", "provider"]
    search_fields = ["reference", "email", "first_name", "last_name"]
    search_backend_name = None
    inspect_view_enabled = True
    inspect_template_name = "dashboard/recurring_inspect.html"
    list_export = ["reference", "created_at", "first_name", "last_name", "email", "amount", "currency", "provider",
                   "status", "next_charge_date", "appeal_code"]
    export_filename = "monthly-gifts"


class GiftOrderViewSet(ModelViewSet):
    model = GiftOrder
    icon = "pick"
    menu_label = "Gift orders"
    add_to_admin_menu = False
    form_fields = ["status"]
    list_display = ["reference", "email", Column("display_total", label="Total"), "status", DateColumn("created_at")]
    list_filter = ["status", "currency"]
    search_fields = ["reference", "email"]
    search_backend_name = None
    inspect_view_enabled = True
    list_export = ["reference", "created_at", "first_name", "last_name", "email", "total", "currency", "status"]


class SubscriberViewSet(ModelViewSet):
    model = Subscriber
    icon = "mail"
    menu_label = "Newsletter subscribers"
    add_to_admin_menu = False
    form_fields = ["first_name", "last_name", "email", "status"]
    list_display = ["email", "first_name", "last_name", "status", "sync_status", DateColumn("created_at")]
    list_filter = ["status", "sync_status"]
    search_fields = ["email", "first_name", "last_name"]
    search_backend_name = None
    list_export = ["email", "first_name", "last_name", "phone", "status", "consent_at", "source_page", "created_at"]
    export_filename = "subscribers"


class WebhookEventViewSet(ModelViewSet):
    model = WebhookEvent
    icon = "code"
    menu_label = "Payment webhook log"
    add_to_admin_menu = False
    form_fields = ["error"]
    list_display = ["provider", "event_type", "event_id", BooleanColumn("ok", label="Processed OK"), DateColumn("received_at")]
    list_filter = ["provider", "event_type"]
    search_fields = ["event_id", "event_type"]
    search_backend_name = None
    inspect_view_enabled = True
    inspect_template_name = "dashboard/webhook_inspect.html"


class ReportQueueViewSet(ModelViewSet):
    model = FundraiserReport
    icon = "warning"
    menu_label = "Fundraiser reports"
    add_to_admin_menu = False
    form_fields = ["resolved"]
    list_display = ["fundraiser", "reason", BooleanColumn("resolved"), DateColumn("created_at")]
    list_filter = ["resolved"]


class ECardViewSet(ModelViewSet):
    model = ECard
    icon = "mail"
    menu_label = "E-cards"
    add_to_admin_menu = False
    form_fields = ["recipient_name", "recipient_email", "message", "send_at", "status"]
    list_display = ["recipient_email", "card_type", "sender_name", "status", DateColumn("send_at", label="Send at")]
    list_filter = ["status", "card_type"]
    search_fields = ["recipient_email", "sender_name", "recipient_name"]
    search_backend_name = None


donation_viewset = DonationViewSet("donations")
recurring_viewset = RecurringGiftViewSet("monthly_gifts")
gift_order_viewset = GiftOrderViewSet("gift_orders")
subscriber_viewset = SubscriberViewSet("subscribers")
webhook_viewset = WebhookEventViewSet("webhook_events")
report_queue_viewset = ReportQueueViewSet("fundraiser_reports")
ecard_viewset = ECardViewSet("ecards")

bank_account_viewset = BankAccountViewSet()
appeal_viewset = AppealViewSet()
gift_item_viewset = GiftItemViewSet()
