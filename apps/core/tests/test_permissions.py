from __future__ import annotations

from apps.core.permissions import user_matches
from apps.users.tests.factories import UserFactory


def test_user_matches_candidate_user(db) -> None:
    user = UserFactory()

    assert user_matches(user, candidate=user) is True


def test_user_matches_user_id(db) -> None:
    user = UserFactory()

    assert user_matches(user, user_id=user.pk) is True
    assert user_matches(user, user_id=None) is False
