from django.urls import path

from . import views

app_name = "giving"

urlpatterns = [
    path("", views.donate_page, name="donate"),
    path("modal/", views.donate_modal, name="modal"),
    path("checkout/", views.checkout, name="checkout"),
    path("return/<str:reference>/", views.donation_return, name="return"),
    path("status/<str:reference>/", views.donation_status, name="status"),
    path("bank-transfer/", views.bank_transfer_notice, name="bank_notice"),
    path("gifts/cart/", views.cart_view, name="cart"),
    path("gifts/cart/update/", views.cart_update, name="cart_update"),
    path("gifts/checkout/", views.gift_checkout, name="gift_checkout"),
]
