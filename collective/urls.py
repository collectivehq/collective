"""Root URL routing for the Collective project."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("", include("apps.pages.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("apps.users.urls")),
    path("spaces/", include("apps.spaces.urls")),
    path("spaces/", include("apps.discussions.urls")),
    path("spaces/", include("apps.posts.urls")),
    path("spaces/", include("apps.opinions.urls")),
    path("spaces/", include("apps.reactions.urls")),
    path("spaces/", include("apps.subscriptions.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
