from __future__ import annotations

from apps.invitations import views
from django.urls import path

app_name = "invitations"

urlpatterns = [
    path("<uuid:space_id>/invitations/bulk/", views.invitation_bulk_create, name="invitation_bulk_create"),
    path("<uuid:space_id>/invitations/resend/", views.invitation_resend_pending, name="invitation_resend_pending"),
    path(
        "<uuid:space_id>/invitations/<uuid:invite_id>/reinvite/",
        views.invitation_reinvite,
        name="invitation_reinvite",
    ),
    path("<uuid:space_id>/invitations/create/", views.invite_create, name="invite_create"),
    path("<uuid:space_id>/invitations/<uuid:invite_id>/delete/", views.invite_delete, name="invite_delete"),
    path("<uuid:space_id>/invitations/<uuid:invite_id>/accept/", views.invite_accept, name="invite_accept"),
    path("<uuid:space_id>/invitations/<uuid:invite_id>/reject/", views.invite_reject, name="invite_reject"),
]
