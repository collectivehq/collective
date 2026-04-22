from __future__ import annotations

from apps.users.models import User


def user_matches(user: User, *, candidate: User | None = None, user_id: object | None = None) -> bool:
    """Return whether the supplied user matches a candidate user or user id."""
    if candidate is not None:
        return user.pk == candidate.pk
    if user_id is None:
        return False
    return user.pk == user_id
