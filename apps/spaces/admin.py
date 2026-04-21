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
    search_fields = ("title",)
    inlines = [RoleInline, SpaceParticipantInline]
    raw_id_fields = ("created_by", "root_discussion")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "label",
        "space",
        "can_post",
        "can_view_drafts",
        "can_resolve",
        "can_shape_tree",
        "can_reorganise",
    )
    list_filter = ("can_post", "can_view_drafts", "can_resolve", "can_shape_tree")


@admin.register(SpaceParticipant)
class SpaceParticipantAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "space", "role", "joined_at")
    raw_id_fields = ("user", "space", "role")
