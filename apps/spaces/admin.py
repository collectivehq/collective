from __future__ import annotations

from django.contrib import admin

from apps.spaces.models import Role, Space, SpaceParticipant


class RoleInline(admin.TabularInline):  # type: ignore[type-arg]
    model = Role
    extra = 0


class SpaceParticipantInline(admin.TabularInline):  # type: ignore[type-arg]
    model = SpaceParticipant
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("title", "lifecycle", "created_by", "created_at")
    list_filter = ("lifecycle",)
    list_select_related = ("created_by",)
    search_fields = ("title", "created_by__email", "created_by__username")
    search_help_text = "Search by title or creator email / username."
    readonly_fields = ("created_at", "updated_at")
    inlines = [RoleInline, SpaceParticipantInline]
    raw_id_fields = ("created_by", "root_discussion")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "label",
        "space",
        "post_highlight_color",
        "can_post",
        "can_edit_others_post",
        "can_create_discussion",
        "can_view_drafts",
        "can_resolve",
        "can_reorganise",
        "can_modify_closed_space",
        "can_manage_participants",
    )
    list_filter = (
        "can_post",
        "can_edit_others_post",
        "can_create_discussion",
        "can_view_drafts",
        "can_resolve",
        "can_reorganise",
        "can_modify_closed_space",
    )
    list_select_related = ("space",)
    search_fields = ("label", "space__title")
    search_help_text = "Search by role label or space title."


@admin.register(SpaceParticipant)
class SpaceParticipantAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "space", "role", "created_at")
    list_select_related = ("user", "space", "role")
    search_fields = ("user__email", "user__username", "space__title")
    search_help_text = "Search by user email / username or space title."
    raw_id_fields = ("user", "space", "role")
