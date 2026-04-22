from __future__ import annotations

from django.urls import path

from apps.posts import views

app_name = "posts"

urlpatterns = [
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/post/", views.post_create, name="post_create"),
    path("<uuid:space_id>/posts/<uuid:post_id>/edit/", views.post_edit, name="post_edit"),
    path("<uuid:space_id>/posts/<uuid:post_id>/delete/", views.post_delete, name="post_delete"),
    path("<uuid:space_id>/posts/<uuid:post_id>/revisions/", views.post_revisions, name="post_revisions"),
    path("<uuid:space_id>/posts/<uuid:post_id>/promote/", views.post_promote, name="post_promote"),
    path("<uuid:space_id>/posts/<uuid:post_id>/publish/", views.post_publish, name="post_publish"),
    path("<uuid:space_id>/links/<uuid:link_id>/delete/", views.link_delete, name="link_delete"),
    path("<uuid:space_id>/items/<uuid:item_id>/move/", views.discussion_item_move, name="discussion_item_move"),
    path(
        "<uuid:space_id>/items/<uuid:item_id>/move-positions/",
        views.discussion_item_move_positions,
        name="discussion_item_move_positions",
    ),
    path("<uuid:space_id>/upload/", views.image_upload, name="image_upload"),
]
