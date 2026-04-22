from __future__ import annotations

from django.urls import path

from apps.opinions import views

app_name = "opinions"

urlpatterns = [
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/opinion/", views.toggle_opinion, name="toggle_opinion"),
]
