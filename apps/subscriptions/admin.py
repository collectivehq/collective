from __future__ import annotations

from django.contrib import admin

from apps.subscriptions.models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("participant", "node", "created_at")
    raw_id_fields = ("participant", "node")
