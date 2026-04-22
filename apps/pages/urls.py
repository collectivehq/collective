from __future__ import annotations

from apps.pages import views
from django.urls import path

app_name = "pages"

urlpatterns = [
    path("", views.landing, name="home"),
]
