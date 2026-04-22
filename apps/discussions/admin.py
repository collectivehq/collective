from __future__ import annotations

from django.contrib import admin

from apps.discussions.models import Discussion


@admin.register(Discussion)
class DiscussionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("label", "space", "depth", "resolution_type", "created_at", "deleted_at")
    list_filter = ("space", "resolution_type", "deleted_at")
    list_select_related = ("space", "resolved_by")
    search_fields = ("label", "space__title", "resolved_by__email")
    search_help_text = "Search by discussion label, space title, or resolver email."
    readonly_fields = ("created_at", "updated_at", "depth", "numchild", "path")
    raw_id_fields = ("space", "resolved_by")
