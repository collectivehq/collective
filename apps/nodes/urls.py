from django.urls import path

from apps.nodes import views

app_name = "nodes"

urlpatterns = [
    path("<uuid:space_id>/tree/", views.discussion_tree, name="discussion_tree"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/", views.discussion_detail, name="discussion_detail"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/edit/", views.discussion_edit, name="discussion_edit"),
    path("<uuid:space_id>/discussions/create/", views.discussion_create, name="discussion_create"),
    path("<uuid:space_id>/discussions/reorder/", views.tree_reorder, name="tree_reorder"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/post/", views.post_create, name="post_create"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/move/", views.discussion_move, name="discussion_move"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/reopen/", views.discussion_reopen, name="discussion_reopen"),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/resolve/", views.discussion_resolve, name="discussion_resolve"
    ),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/delete/", views.discussion_delete, name="discussion_delete"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/merge/", views.discussion_merge, name="discussion_merge"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/split/", views.discussion_split, name="discussion_split"),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/reorder-children/",
        views.discussion_children_reorder,
        name="discussion_children_reorder",
    ),
    path("<uuid:space_id>/posts/<uuid:post_id>/edit/", views.post_edit, name="post_edit"),
    path("<uuid:space_id>/posts/<uuid:post_id>/delete/", views.post_delete, name="post_delete"),
    path("<uuid:space_id>/posts/<uuid:post_id>/revisions/", views.post_revisions, name="post_revisions"),
    path("<uuid:space_id>/posts/<uuid:post_id>/move/", views.post_move, name="post_move"),
    path("<uuid:space_id>/posts/<uuid:post_id>/move-positions/", views.post_move_positions, name="post_move_positions"),
    path("<uuid:space_id>/posts/<uuid:post_id>/promote/", views.post_promote, name="post_promote"),
    path("<uuid:space_id>/posts/<uuid:post_id>/publish/", views.post_publish, name="post_publish"),
    path("<uuid:space_id>/links/<uuid:link_id>/delete/", views.link_delete, name="link_delete"),
    path("<uuid:space_id>/upload/", views.image_upload, name="image_upload"),
]
