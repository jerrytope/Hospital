from django.urls import path

from . import views

app_name = "fundraising"

urlpatterns = [
    path("", views.fundraiser_list, name="list"),
    path("start/", views.start, name="start"),
    path("<slug:slug>/", views.fundraiser_detail, name="detail"),
    path("<slug:slug>/report/", views.report_fundraiser, name="report"),
]
