from __future__ import annotations

from django.urls import path

from apps.reactions import views

app_name = "reactions"

urlpatterns = [
    path("<uuid:space_id>/posts/<uuid:post_id>/react/", views.toggle_reaction, name="toggle_reaction"),
]
