from __future__ import annotations

from django.contrib import admin

from apps.nodes.models import Node, PostRevision


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("label", "node_type", "space", "depth", "child_count", "created_at")
    list_filter = ("node_type", "space")
    search_fields = ("label",)
    raw_id_fields = ("space", "author", "resolved_by", "target")


@admin.register(PostRevision)
class PostRevisionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("post", "created_at")
    raw_id_fields = ("post",)
