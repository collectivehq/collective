from __future__ import annotations

from django.urls import path

from apps.users import views

app_name = "users"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
]
