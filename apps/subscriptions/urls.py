from django.urls import path

from apps.subscriptions import views

app_name = "subscriptions"

urlpatterns = [
    path("<uuid:space_id>/nodes/<uuid:node_id>/subscribe/", views.toggle_subscription, name="toggle_subscription"),
]
