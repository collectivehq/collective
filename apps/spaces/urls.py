from __future__ import annotations

from django.urls import path

from apps.spaces import views

app_name = "spaces"

urlpatterns = [
    path("", views.space_list, name="list"),
    path("create/", views.space_create, name="create"),
    path("<uuid:space_id>/", views.space_detail, name="detail"),
    path("<uuid:space_id>/join/", views.space_join, name="join"),
    path("<uuid:space_id>/settings/", views.space_settings, name="settings"),
    path("<uuid:space_id>/participants/", views.space_participants, name="participants"),
    path("<uuid:space_id>/participants/add/", views.participant_add, name="participant_add"),
    path(
        "<uuid:space_id>/participants/<uuid:participant_id>/remove/",
        views.participant_remove,
        name="participant_remove",
    ),
    path(
        "<uuid:space_id>/participants/<uuid:participant_id>/role/",
        views.participant_role_update,
        name="participant_role_update",
    ),
    path("<uuid:space_id>/permissions/", views.space_permissions, name="permissions"),
    path("<uuid:space_id>/roles/create/", views.role_create, name="role_create"),
    path("<uuid:space_id>/roles/<uuid:role_id>/update/", views.role_update, name="role_update"),
    path("<uuid:space_id>/roles/<uuid:role_id>/delete/", views.role_delete, name="role_delete"),
    path("<uuid:space_id>/roles/<uuid:role_id>/set-default/", views.role_set_default, name="role_set_default"),
    path("<uuid:space_id>/invites/create/", views.invite_create, name="invite_create"),
    path("<uuid:space_id>/invites/<uuid:invite_id>/delete/", views.invite_delete, name="invite_delete"),
    path("<uuid:space_id>/invite/<uuid:invite_id>/", views.invite_accept, name="invite_accept"),
]
