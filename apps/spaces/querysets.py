from __future__ import annotations

from typing import TYPE_CHECKING, Self, TypeVar

from django.db import models
from django.db.models import Q
from django.utils import timezone

if TYPE_CHECKING:
    from apps.users.models import User


SpaceModelT = TypeVar("SpaceModelT", bound=models.Model)


class SpaceQuerySet(models.QuerySet[SpaceModelT]):
    def active(self) -> Self:
        now = timezone.now()
        return self.filter(
            lifecycle="open",
            deleted_at__isnull=True,
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        )

    def for_user(self, user: User) -> Self:
        return self.filter(participants__user=user, deleted_at__isnull=True).distinct()
