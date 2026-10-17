from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls

from apps.accounts import views as account_views
from apps.core import views as core_views

admin_prefix = settings.ADMIN_PATH

urlpatterns = [
    # Owner/staff admin and its two-factor screens
    path(f"{admin_prefix}/2fa/setup/", account_views.two_factor_setup, name="two_factor_setup"),
    path(f"{admin_prefix}/2fa/verify/", account_views.two_factor_verify, name="two_factor_verify"),
    path(f"{admin_prefix}/", include(wagtailadmin_urls)),
    path(f"{settings.DJANGO_ADMIN_PATH}/", admin.site.urls),
    path("documents/", include(wagtaildocs_urls)),
    # Public features
    path("search/", core_views.search, name="search"),
    path("cookies/accept/", core_views.cookie_consent, name="cookie_consent"),
    path("newsletter/", include("apps.newsletter.urls")),
    path("donate/", include("apps.giving.urls")),
    path("payments/", include("apps.payments.urls")),
    path("fundraise/", include("apps.fundraising.urls")),
    path("account/", include("apps.accounts.urls")),
    path("account/", include("allauth.urls")),
    path("sitemap.xml", sitemap),
    path("robots.txt", core_views.robots_txt),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [path("", include(wagtail_urls))]
