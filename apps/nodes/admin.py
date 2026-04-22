from __future__ import annotations

from django.contrib import admin

from apps.nodes.models import Node, PostRevision


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("label", "node_type", "space", "depth", "child_count", "created_at")
    list_filter = ("node_type", "space")
    list_select_related = ("space", "author")
    search_fields = ("label", "space__title", "author__email")
    search_help_text = "Search by label, space title, or author email."
    readonly_fields = ("created_at", "updated_at", "depth", "numchild", "path")
    raw_id_fields = ("space", "author", "resolved_by", "target")


@admin.register(PostRevision)
class PostRevisionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("post", "created_at")
    list_select_related = ("post",)
    readonly_fields = ("created_at",)
    raw_id_fields = ("post",)
