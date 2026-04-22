from __future__ import annotations

from django.contrib import admin

from apps.subscriptions.models import Notification, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("created_by", "discussion", "created_at")
    list_select_related = ("created_by", "discussion")
    search_fields = ("created_by__email", "discussion__label")
    search_help_text = "Search by subscriber email or discussion label."
    readonly_fields = ("created_at",)
    raw_id_fields = ("created_by", "discussion")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("recipient", "event_type", "discussion", "created_by", "created_at", "read_at")
    list_filter = ("event_type", "read_at")
    list_select_related = ("recipient", "discussion", "created_by")
    search_fields = ("recipient__email", "created_by__email", "discussion__label")
    search_help_text = "Search by recipient email, actor email, or discussion label."
    readonly_fields = ("created_at",)
    raw_id_fields = ("recipient", "discussion", "post", "created_by")
