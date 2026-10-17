from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="account_dashboard"),
    path("profile/", views.profile, name="account_profile"),
    path("donations/", views.donations, name="account_donations"),
    path("donations/<str:reference>/receipt.pdf", views.receipt_download, name="account_receipt"),
    path("statements/<int:year>.pdf", views.statement_download, name="account_statement"),
    path("monthly/", views.monthly, name="account_monthly"),
    path("monthly/<str:reference>/", views.monthly_action, name="account_monthly_action"),
    path("ecards/", views.ecards, name="account_ecards"),
    path("ecards/<int:pk>/", views.ecard_action, name="account_ecard_action"),
    path("gift-orders/", views.gift_orders, name="account_gift_orders"),
    path("fundraisers/", views.fundraisers, name="account_fundraisers"),
    path("fundraisers/new/", views.fundraiser_edit, name="account_fundraiser_create"),
    path("fundraisers/<int:pk>/edit/", views.fundraiser_edit, name="account_fundraiser_edit"),
    path("fundraisers/<int:pk>/", views.fundraiser_manage, name="account_fundraiser_manage"),
    path("email-preferences/", views.email_preferences, name="account_email_prefs"),
    path("export/", views.export_data, name="account_export"),
    path("delete/", views.delete_account, name="account_delete"),
]
