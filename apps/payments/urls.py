from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("webhooks/paystack/", views.paystack_webhook, name="paystack_webhook"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
    path("test-checkout/<str:reference>/", views.fake_checkout, name="fake_checkout"),
    path("test-renewal/<str:reference>/", views.fake_renewal, name="fake_renewal"),
]
