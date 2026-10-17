import pytest
from wagtail.models import Page, Site

from apps.accounts.models import User
from apps.core.models import FolderPage
from apps.emergencies.models import EmergencyPage
from apps.pages.models import HomePage


@pytest.fixture
def home(db):
    root = Page.get_first_root_node()
    Page.objects.filter(depth=2).delete()
    home = HomePage(title="Home", slug="home")
    root.add_child(instance=home)
    Site.objects.all().delete()
    Site.objects.create(hostname="testserver", root_page=home, is_default_site=True, site_name="Test")
    return home


@pytest.fixture
def emergency(home):
    folder = FolderPage(title="Emergency response", slug="emergency-response")
    home.add_child(instance=folder)
    page = EmergencyPage(title="Flood Response", slug="floods", status="active", appeal_code="FLOODS")
    folder.add_child(instance=page)
    return page


@pytest.fixture
def owner(db):
    return User.objects.create_superuser(email="owner@test.org", password="pass-12345-ok", first_name="Site", last_name="Owner")


@pytest.fixture
def supporter(db):
    from allauth.account.models import EmailAddress

    user = User.objects.create_user(email="ada@test.org", password="pass-12345-ok", first_name="Ada", last_name="Obi")
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


@pytest.fixture
def donation_data():
    return {
        "currency": "NGN",
        "frequency": "one_time",
        "amount": "25000",
        "first_name": "Ada",
        "last_name": "Obi",
        "email": "ada@test.org",
        "appeal_code": "home-hero",
    }


@pytest.fixture(autouse=True)
def run_on_commit_immediately(monkeypatch):
    """Tests run inside a transaction that never commits, so fire on_commit callbacks at once."""
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
