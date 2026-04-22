from __future__ import annotations

from django.contrib import admin

from apps.opinions.models import Opinion


@admin.register(Opinion)
class OpinionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("created_by", "discussion", "opinion_type", "created_at")
    list_filter = ("opinion_type",)
    list_select_related = ("created_by", "discussion")
    readonly_fields = ("created_at",)
    raw_id_fields = ("created_by", "discussion")
