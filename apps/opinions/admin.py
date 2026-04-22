from __future__ import annotations

from django.contrib import admin

from apps.opinions.models import Opinion, Reaction


@admin.register(Opinion)
class OpinionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("participant", "node", "opinion_type", "created_at", "updated_at")
    list_filter = ("opinion_type",)
    list_select_related = ("participant", "node")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("participant", "node")


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("participant", "post", "reaction_type", "created_at")
    list_filter = ("reaction_type",)
    list_select_related = ("participant", "post")
    readonly_fields = ("created_at",)
    raw_id_fields = ("participant", "post")
