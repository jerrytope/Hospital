from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.fundraising.models import Fundraiser
from apps.giving import services
from apps.giving.models import BankAccount, Donation, ECard, RecurringGift

pytestmark = pytest.mark.django_db


def make_paid_donation(user, **extra):
    d = services.create_donation(
        amount=Decimal("10000"), currency="NGN", frequency=extra.pop("frequency", "one_time"), provider="fake",
        donor={"first_name": user.first_name, "last_name": user.last_name, "email": user.email}, user=user, **extra,
    )
    services.donation_succeeded(d)
    d.refresh_from_db()
    return d


# --- Owner admin --------------------------------------------------------------------------


def test_admin_requires_login(client, home):
    resp = client.get("/admin/")
    assert resp.status_code == 302 and "/admin/login/" in resp["Location"]


def test_admin_requires_2fa_after_password(client, home, owner):
    client.force_login(owner)
    resp = client.get("/admin/")
    assert resp.status_code == 302 and "/admin/2fa/setup/" in resp["Location"]
    setup = client.get(resp["Location"])
    assert setup.status_code == 200 and b"<svg" in setup.content


def test_admin_2fa_verification_flow(client, home, owner):
    from django_otp.oath import totp
    from django_otp.plugins.otp_totp.models import TOTPDevice

    client.force_login(owner)
    client.get("/admin/2fa/setup/")
    device = TOTPDevice.objects.get(user=owner)
    code = str(totp(device.bin_key)).zfill(6)
    resp = client.post("/admin/2fa/setup/", {"token": code})
    assert resp.status_code == 302
    assert client.get("/admin/").status_code == 200
    # A new session must enter a code
    client.logout()
    client.force_login(owner)
    assert "/admin/2fa/verify/" in client.get("/admin/")["Location"]


def test_owner_screens_load(client, home, owner, settings):
    settings.ADMIN_REQUIRE_2FA = False
    client.force_login(owner)
    for url in ["/admin/", "/admin/giving/", "/admin/giving/appeals-report/", "/admin/bank-transfers/",
                "/admin/fundraisers/", "/admin/donations/", "/admin/monthly_gifts/", "/admin/subscribers/",
                "/admin/snippets/giving/bankaccount/", "/admin/settings/core/organisationsettings/",
                "/admin/settings/core/navigationsettings/", "/admin/settings/giving/donationsettings/"]:
        resp = client.get(url, follow=True)
        assert resp.status_code == 200, url


def test_owner_adds_bank_account_and_it_shows_on_site(client, home, owner, settings):
    settings.ADMIN_REQUIRE_2FA = False
    client.force_login(owner)
    resp = client.post("/admin/snippets/giving/bankaccount/add/", {
        "bank_name": "Owner Bank", "account_name": "Haven", "account_number": "2468013579", "currency": "NGN",
        "show_on_donate": "on", "active": "on", "order": "0",
    })
    assert resp.status_code == 302, resp.content[:800]
    assert BankAccount.objects.filter(account_number="2468013579").exists()
    client.logout()
    assert b"2468013579" in client.get(reverse("giving:donate")).content


def test_staff_without_permission_cannot_see_donations(client, home, settings):
    from django.contrib.auth.models import Group, Permission

    from apps.accounts.models import User

    settings.ADMIN_REQUIRE_2FA = False
    editor = User.objects.create_user(email="editor@test.org", password="x-12345-xx", is_staff=True)
    group = Group.objects.create(name="Editors test")
    group.permissions.add(Permission.objects.get(codename="access_admin"))
    editor.groups.add(group)
    client.force_login(editor)
    for url in ("/admin/giving/", "/admin/bank-transfers/", "/admin/donations/"):
        resp = client.get(url, follow=True)
        # Wagtail sends refused staff back to the dashboard with an error message.
        assert resp.redirect_chain and resp.redirect_chain[-1][0] == "/admin/", url
        assert b"Giving overview" not in resp.content


# --- Supporter account area -------------------------------------------------------------------


def test_account_pages_require_login(client, home):
    assert client.get(reverse("account_dashboard")).status_code == 302


def test_supporter_sees_only_own_donations_and_receipts(client, home, supporter):
    from apps.accounts.models import User

    mine = make_paid_donation(supporter)
    other = User.objects.create_user(email="other@test.org", password="x-12345-xx", first_name="O", last_name="T")
    theirs = make_paid_donation(other)
    client.force_login(supporter)
    assert client.get(reverse("account_donations")).status_code == 200
    assert client.get(reverse("account_receipt", args=[mine.reference])).status_code == 200
    assert client.get(reverse("account_receipt", args=[theirs.reference])).status_code == 404


def test_supporter_manages_monthly_gift(client, home, supporter):
    d = make_paid_donation(supporter, frequency="monthly")
    gift = d.recurring_gift
    client.force_login(supporter)
    client.post(reverse("account_monthly_action", args=[gift.reference]), {"action": "change", "amount": "15000", "day": "12"})
    gift.refresh_from_db()
    assert gift.amount == Decimal("15000") and gift.day_of_month == 12
    client.post(reverse("account_monthly_action", args=[gift.reference]), {"action": "pause"})
    gift.refresh_from_db()
    assert gift.status == "paused"
    client.post(reverse("account_monthly_action", args=[gift.reference]), {"action": "resume"})
    gift.refresh_from_db()
    assert gift.status == "active"
    client.post(reverse("account_monthly_action", args=[gift.reference]), {"action": "cancel"})
    gift.refresh_from_db()
    assert gift.status == "cancelled"
    # Cannot change after cancel
    client.post(reverse("account_monthly_action", args=[gift.reference]), {"action": "change", "amount": "99000"})
    gift.refresh_from_db()
    assert gift.amount == Decimal("15000")


def test_supporter_edits_ecard_until_sent(client, home, supporter):
    future = timezone.now() + timezone.timedelta(days=5)
    d = make_paid_donation(supporter, tribute={"card_type": "honor", "honoree_name": "Dad", "sender_name": "Ada Obi",
                                                "recipient_name": "Dad", "recipient_email": "dad@test.org", "send_at": future})
    card = d.ecards.get()
    client.force_login(supporter)
    new_date = (timezone.localdate() + timezone.timedelta(days=2)).isoformat()
    client.post(reverse("account_ecard_action", args=[card.pk]), {
        "action": "edit", "recipient_name": "Daddy", "recipient_email": "daddy@test.org", "message": "Love you", "send_date": new_date})
    card.refresh_from_db()
    assert card.recipient_email == "daddy@test.org" and card.message == "Love you"
    card.status = "sent"
    card.save()
    client.post(reverse("account_ecard_action", args=[card.pk]), {
        "action": "edit", "recipient_name": "X", "recipient_email": "x@test.org", "message": "", "send_date": new_date})
    card.refresh_from_db()
    assert card.recipient_email == "daddy@test.org"


def test_fundraiser_lifecycle(client, home, supporter, owner, settings):
    client.force_login(supporter)
    resp = client.post(reverse("account_fundraiser_create"), {
        "title": "My birthday for clean water", "story": "Help me raise money", "goal": "100000", "currency": "NGN", "submit": "1"})
    assert resp.status_code == 302
    f = Fundraiser.objects.get()
    assert f.status == "pending"
    client.logout()
    assert client.get(f.get_absolute_url()).status_code == 404  # not public until approved
    settings.ADMIN_REQUIRE_2FA = False
    client.force_login(owner)
    client.post(reverse("dashboard_fundraiser_action", args=[f.pk]), {"action": "approve"})
    f.refresh_from_db()
    assert f.status == "live" and f.ever_approved
    client.logout()
    assert client.get(f.get_absolute_url()).status_code == 200
    # A donation to it updates the total
    d = services.create_donation(amount=Decimal("20000"), currency="NGN", frequency="one_time", provider="fake",
                                 donor={"first_name": "G", "last_name": "H", "email": "g@test.org"}, fundraiser=f)
    services.donation_succeeded(d)
    assert f.raised == Decimal("20000") and f.percent == 20
    # Owner edits after approval go live but are flagged
    client.force_login(supporter)
    client.post(reverse("account_fundraiser_edit", args=[f.pk]), {
        "title": "My birthday for clean water!", "story": "Updated", "goal": "100000", "currency": "NGN"})
    f.refresh_from_db()
    assert f.status == "live" and f.edited_since_review


def test_account_deletion_anonymises_but_keeps_records(client, home, supporter):
    d = make_paid_donation(supporter)
    client.force_login(supporter)
    client.post(reverse("account_delete"), {"confirm": "DELETE"})
    d.refresh_from_db()
    assert d.user is None and d.email.endswith("@deleted.invalid") and d.status == "succeeded"


# --- Newsletter -------------------------------------------------------------------------------


def test_newsletter_signup_and_token_unsubscribe(client, home):
    from apps.newsletter.models import Subscriber

    resp = client.post(reverse("newsletter:subscribe"), {"first_name": "Ada", "last_name": "Obi", "email": "Ada@Test.org", "source_page": "/"}, HTTP_HX_REQUEST="true")
    assert b"Thank you" in resp.content
    sub = Subscriber.objects.get(email="ada@test.org")
    assert sub.consent_at and sub.sync_status == "skipped"
    client.post(reverse("newsletter:unsubscribe", args=[sub.unsubscribe_token()]))
    sub.refresh_from_db()
    assert sub.status == "unsubscribed"
    assert client.get(reverse("newsletter:unsubscribe", args=["bad-token"])).status_code == 200


def test_newsletter_honeypot(client, home):
    from apps.newsletter.models import Subscriber

    client.post(reverse("newsletter:subscribe"), {"first_name": "Bot", "last_name": "Bot", "email": "bot@test.org", "website": "spam"})
    assert not Subscriber.objects.exists()
