from __future__ import annotations

from django.urls import path

from apps.subscriptions import views

app_name = "subscriptions"

urlpatterns = [
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/subscribe/",
        views.toggle_subscription,
        name="toggle_subscription",
    ),
    path("notifications/", views.notification_center, name="notifications"),
    path("notifications/mark-all-read/", views.notification_mark_all_read, name="notification_mark_all_read"),
    path("notifications/<uuid:notification_id>/open/", views.notification_open, name="notification_open"),
]
