from __future__ import annotations

from django.contrib import admin

from apps.subscriptions.models import Notification, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("participant", "node", "created_at")
    list_select_related = ("participant", "node")
    search_fields = ("participant__user__email", "node__label")
    search_help_text = "Search by participant email or node label."
    readonly_fields = ("created_at",)
    raw_id_fields = ("participant", "node")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("participant", "event_type", "node", "actor", "created_at", "read_at")
    list_filter = ("event_type", "read_at")
    list_select_related = ("participant", "node", "actor")
    search_fields = ("participant__user__email", "actor__email", "node__label")
    search_help_text = "Search by participant email, actor email, or node label."
    readonly_fields = ("created_at",)
    raw_id_fields = ("participant", "node", "post", "actor")
