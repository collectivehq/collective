from __future__ import annotations

from apps.invitations.models import SpaceInvite
from django.contrib import admin


@admin.register(SpaceInvite)
class SpaceInviteAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("space", "role", "email", "created_by", "created_at", "expires_at")
    list_select_related = ("space", "role", "created_by", "accepted_by", "rejected_by")
    search_fields = ("email", "space__title", "created_by__email", "created_by__username")
    search_help_text = "Search by invitee email, space title, or creator email / username."
    readonly_fields = ("created_at", "last_sent_at", "expires_at", "accepted_at", "rejected_at")
    raw_id_fields = ("space", "role", "created_by", "accepted_by", "rejected_by")
