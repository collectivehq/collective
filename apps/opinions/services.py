from __future__ import annotations

import uuid

from django.db import transaction
from django.db.models import Count

from apps.discussions.models import Discussion
from apps.opinions.models import Opinion
from apps.spaces.models import Space
from apps.spaces.services import touch_space
from apps.users.models import User


def toggle_opinion(
    *,
    user: User,
    discussion: Discussion,
    opinion_type: str,
) -> Opinion | None:
    space = Space.objects.only("pk", "opinion_types").get(pk=discussion.space_id)
    if opinion_type not in space.opinion_types:
        msg = f"Opinion type '{opinion_type}' is not enabled for this space"
        raise ValueError(msg)

    with transaction.atomic():
        existing = Opinion.objects.select_for_update().filter(created_by=user, discussion=discussion).first()
        if existing:
            if existing.opinion_type == opinion_type:
                existing.delete()
                touch_space(space=space)
                return None
            existing.opinion_type = opinion_type
            existing.save(update_fields=["opinion_type"])
            touch_space(space=space)
            return existing

        opinion = Opinion.objects.create(
            created_by=user,
            discussion=discussion,
            opinion_type=opinion_type,
        )
        touch_space(space=space)
        return opinion


def get_opinion_counts(discussion: Discussion) -> dict[str, int]:
    qs = Opinion.objects.filter(discussion=discussion).values("opinion_type").annotate(count=Count("id"))
    return {row["opinion_type"]: row["count"] for row in qs}


def get_user_opinion_type(*, user: User, discussion: Discussion) -> str | None:
    opinion = (
        Opinion.objects.filter(created_by=user, discussion=discussion).values_list("opinion_type", flat=True).first()
    )
    return opinion


def get_opinion_counts_batch(discussion_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    qs = (
        Opinion.objects.filter(discussion_id__in=discussion_ids)
        .values("discussion_id", "opinion_type")
        .annotate(count=Count("id"))
    )
    result: dict[uuid.UUID, dict[str, int]] = {}
    for row in qs:
        result.setdefault(row["discussion_id"], {})[row["opinion_type"]] = row["count"]
    return result
