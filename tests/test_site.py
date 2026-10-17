"""Whole-site checks against the seeded demo content."""
import pytest
from django.core.management import call_command
from wagtail.models import Page

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(db):
    call_command("seed_demo", "--reset", verbosity=0)
    return True


def test_every_live_page_renders(client, seeded):
    from apps.core.models import FolderPage

    failures = []
    for page in Page.objects.live().filter(depth__gte=2).specific():
        resp = client.get(page.url)
        expected = 302 if isinstance(page, FolderPage) else 200
        if resp.status_code != expected:
            failures.append((page.url, resp.status_code))
    assert not failures


def test_stories_filters_are_in_the_url(client, seeded):
    from apps.programs.models import ProgramPage
    from apps.stories.models import StoryPage

    program = ProgramPage.objects.get(slug="mental-health")
    expected = StoryPage.objects.live().filter(programs=program).count()
    resp = client.get(f"/stories-and-news/?program={program.slug}")
    assert resp.status_code == 200
    assert resp.context["page_obj"].paginator.count == expected
    resp = client.get("/stories-and-news/?type=press")
    assert all(s.story_type == "press" for s in resp.context["results"])


def test_header_menu_is_dynamic(client, seeded):
    from apps.emergencies.models import EmergencyPage

    content = client.get("/").content.decode()
    first = EmergencyPage.objects.live().filter(status="active").order_by("-featured", "-year_start").first()
    assert first.title in content
    assert "Who We Are" in content and "Donate Now" in content


def test_homepage_donate_buttons_carry_appeal_codes(client, seeded):
    content = client.get("/").content.decode()
    for code in ("HOME-HERO", "HOME-BAND", "HEADER", "FOOTER"):
        assert f"appeal={code}" in content


def test_search(client, seeded):
    resp = client.get("/search/?q=water")
    assert resp.status_code == 200 and resp.context["page_obj"].paginator.count > 0


def test_sitemap_and_robots(client, seeded):
    assert client.get("/sitemap.xml").status_code == 200
    assert b"Disallow: /admin/" in client.get("/robots.txt").content
