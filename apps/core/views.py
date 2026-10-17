from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from wagtail.contrib.search_promotions.models import Query
from wagtail.models import Page


def search(request):
    query = (request.GET.get("q") or "").strip()
    results = Page.objects.none()
    promotions = []
    if query:
        results = Page.objects.live().public().not_type(*_hidden_types()).specific().search(query)
        q = Query.get(query)
        q.add_hit()
        promotions = q.editors_picks.all()
    paginator = Paginator(results, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    template = "search/partials/live_results.html" if request.headers.get("HX-Request") else "search/search.html"
    return render(
        request,
        template,
        {"query": query, "page_obj": page_obj, "results": page_obj.object_list, "promotions": promotions},
    )


def _hidden_types():
    from apps.core.models import FolderPage

    return (FolderPage,)


@require_POST
def cookie_consent(request):
    choice = "accepted" if request.POST.get("choice") != "rejected" else "rejected"
    nxt = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = "/"
    if request.headers.get("HX-Request"):
        response = HttpResponse("")
    else:
        response = HttpResponseRedirect(nxt)
    response.set_cookie("cookie_consent", choice, max_age=60 * 60 * 24 * 365, samesite="Lax", secure=not settings.DEBUG)
    return response


def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: /{settings.ADMIN_PATH}/",
        "Disallow: /account/",
        "Disallow: /payments/",
        "Disallow: /search/",
        f"Sitemap: {settings.SITE_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def ratelimited(request, exception=None):
    return render(request, "429.html", status=429)
