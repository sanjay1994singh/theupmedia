from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("cart/", views.cart, name="cart"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("orders/", views.orders, name="orders"),
    path("my-services/", views.my_subscriptions, name="my_subscriptions"),
    path("cart/add/<int:plan_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("wishlist/toggle/<int:plan_id>/", views.toggle_wishlist, name="toggle_wishlist"),
    path("api/create-order/", views.create_order, name="create_order"),
    path("api/verify-payment/", views.verify_payment, name="verify_payment"),
    path("api/payment-failed/", views.payment_failed, name="payment_failed"),
]
