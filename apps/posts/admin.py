from __future__ import annotations

from django.contrib import admin

from apps.posts.models import Link, Post, PostRevision


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("short_content", "space", "author", "is_draft", "sequence_index", "created_at", "updated_at")
    list_filter = ("discussion", "is_draft", "deleted_at")
    list_select_related = ("discussion__space", "created_by")
    search_fields = ("created_by__email", "discussion__space__title")
    search_help_text = "Search by post content, author email, or space title."
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("discussion", "created_by")

    @admin.display(description="Content")
    def short_content(self, obj: Post) -> str:
        text = (obj.content or "").strip()
        return text[:80] + ("..." if len(text) > 80 else "")


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("space", "target", "sequence_index", "created_at", "deleted_at")
    list_filter = ("discussion", "deleted_at")
    list_select_related = ("discussion__space", "discussion", "target", "created_by")
    search_fields = ("discussion__space__title", "target__label")
    search_help_text = "Search by space title or target discussion label."
    readonly_fields = ("created_at",)
    raw_id_fields = ("discussion", "target", "created_by")


@admin.register(PostRevision)
class PostRevisionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("post", "created_by", "created_at")
    list_select_related = ("post", "created_by")
    readonly_fields = ("created_at",)
    raw_id_fields = ("post", "created_by")
