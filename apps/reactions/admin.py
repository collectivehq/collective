from __future__ import annotations

from django.contrib import admin

from apps.reactions.models import Reaction


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("created_by", "post", "reaction_type", "created_at")
    list_filter = ("reaction_type",)
    list_select_related = ("created_by", "post")
    readonly_fields = ("created_at",)
    raw_id_fields = ("created_by", "post")
