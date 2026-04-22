from __future__ import annotations

from django.utils import timezone

from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


def test_active_returns_only_current_open_spaces(db) -> None:
    user = UserFactory()
    active_space = space_services.create_space(title="Active", created_by=user)
    future_space = space_services.create_space(
        title="Future",
        created_by=user,
        starts_at=timezone.now() + timezone.timedelta(hours=1),
    )
    ended_space = space_services.create_space(
        title="Ended",
        created_by=user,
        ends_at=timezone.now() - timezone.timedelta(minutes=1),
    )

    space_services.open_space(space=active_space)
    space_services.open_space(space=future_space)
    space_services.open_space(space=ended_space)

    result_ids = set(Space.objects.active().values_list("pk", flat=True))

    assert active_space.pk in result_ids
    assert future_space.pk not in result_ids
    assert ended_space.pk not in result_ids


def test_active_excludes_closed_spaces(db) -> None:
    user = UserFactory()
    space = space_services.create_space(title="Closed", created_by=user)
    space_services.open_space(space=space)
    space.lifecycle = Space.Lifecycle.CLOSED
    space.save(update_fields=["lifecycle"])

    assert not Space.objects.active().filter(pk=space.pk).exists()


def test_for_user_returns_only_non_deleted_memberships(db) -> None:
    creator = UserFactory()
    joiner = UserFactory()
    member_space = space_services.create_space(title="Member", created_by=creator)
    other_space = space_services.create_space(title="Other", created_by=creator)
    deleted_space = space_services.create_space(title="Deleted", created_by=creator)

    space_services.open_space(space=member_space)
    space_services.open_space(space=other_space)
    space_services.open_space(space=deleted_space)
    space_services.join_space(space=member_space, user=joiner)
    space_services.join_space(space=deleted_space, user=joiner)
    deleted_space.deleted_at = timezone.now()
    deleted_space.save(update_fields=["deleted_at"])

    result_ids = set(Space.objects.for_user(joiner).values_list("pk", flat=True))

    assert member_space.pk in result_ids
    assert other_space.pk not in result_ids
    assert deleted_space.pk not in result_ids
