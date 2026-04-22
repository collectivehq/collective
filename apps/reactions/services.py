from __future__ import annotations

import uuid

from django.db import transaction
from django.db.models import Count

from apps.posts.models import Post
from apps.reactions.models import Reaction
from apps.spaces.models import Space
from apps.spaces.services import touch_space
from apps.users.models import User


def toggle_reaction(
    *,
    user: User,
    post: Post,
    reaction_type: str,
) -> Reaction | None:
    space = Space.objects.only("pk", "reaction_types").get(pk=post.space_id)
    if not space.reaction_types:
        msg = "Reactions are disabled for this space"
        raise ValueError(msg)
    if reaction_type not in space.reaction_types:
        msg = f"{reaction_type.title()} reactions are not enabled for this space"
        raise ValueError(msg)

    with transaction.atomic():
        existing = Reaction.objects.select_for_update().filter(created_by=user, post=post).first()
        if existing:
            if existing.reaction_type == reaction_type:
                existing.delete()
                touch_space(space=space)
                return None
            existing.reaction_type = reaction_type
            existing.save(update_fields=["reaction_type"])
            touch_space(space=space)
            return existing

        reaction = Reaction.objects.create(
            created_by=user,
            post=post,
            reaction_type=reaction_type,
        )
        touch_space(space=space)
        return reaction


def get_user_reactions_batch(*, user: User, post_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    qs = Reaction.objects.filter(created_by=user, post_id__in=post_ids).values_list("post_id", "reaction_type")
    return dict(qs)


def get_reaction_counts_batch(post_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    qs = Reaction.objects.filter(post_id__in=post_ids).values("post_id", "reaction_type").annotate(count=Count("id"))
    result: dict[uuid.UUID, dict[str, int]] = {}
    for row in qs:
        result.setdefault(row["post_id"], {})[row["reaction_type"]] = row["count"]
    return result
