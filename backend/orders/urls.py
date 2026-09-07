from django.urls import path

from .views import checkout_config, create_order


urlpatterns = [
    path("config/", checkout_config, name="checkout-config"),
    path("", create_order, name="create-order"),
]
