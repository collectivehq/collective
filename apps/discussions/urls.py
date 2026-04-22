from __future__ import annotations

from django.urls import path

from apps.discussions import views

app_name = "discussions"

urlpatterns = [
    path("<uuid:space_id>/tree/", views.discussion_tree, name="discussion_tree"),
    path("<uuid:space_id>/discussions/<uuid:discussion_id>/", views.discussion_detail, name="discussion_detail"),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/edit/",
        views.discussion_edit,
        name="discussion_edit",
    ),
    path("<uuid:space_id>/discussions/create/", views.discussion_create, name="discussion_create"),
    path("<uuid:space_id>/discussions/reorder/", views.tree_reorder, name="tree_reorder"),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/move/",
        views.discussion_move,
        name="discussion_move",
    ),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/reopen/",
        views.discussion_reopen,
        name="discussion_reopen",
    ),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/resolve/",
        views.discussion_resolve,
        name="discussion_resolve",
    ),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/delete/",
        views.discussion_delete,
        name="discussion_delete",
    ),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/merge/",
        views.discussion_merge,
        name="discussion_merge",
    ),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/split/",
        views.discussion_split,
        name="discussion_split",
    ),
    path(
        "<uuid:space_id>/discussions/<uuid:discussion_id>/reorder-children/",
        views.discussion_children_reorder,
        name="discussion_children_reorder",
    ),
]
