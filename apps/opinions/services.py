from __future__ import annotations

import uuid

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.nodes.models import Node
from apps.opinions.models import Opinion, Reaction
from apps.spaces.models import Space, SpaceParticipant


def toggle_opinion(
    *,
    participant: SpaceParticipant,
    node: Node,
    opinion_type: str,
) -> Opinion | None:
    space = Space.objects.only("pk", "opinion_types").get(pk=node.space_id)
    if opinion_type not in space.opinion_types:
        msg = f"Opinion type '{opinion_type}' is not enabled for this space"
        raise ValueError(msg)

    with transaction.atomic():
        SpaceParticipant.objects.select_for_update().get(pk=participant.pk)
        existing = Opinion.objects.select_for_update().filter(participant=participant, node=node).first()
        if existing:
            if existing.opinion_type == opinion_type:
                existing.delete()
                Space.objects.filter(pk=space.pk).update(updated_at=timezone.now())
                return None
            existing.opinion_type = opinion_type
            existing.save(update_fields=["opinion_type", "updated_at"])
            Space.objects.filter(pk=space.pk).update(updated_at=timezone.now())
            return existing

        opinion = Opinion.objects.create(
            participant=participant,
            node=node,
            opinion_type=opinion_type,
        )
        Space.objects.filter(pk=space.pk).update(updated_at=timezone.now())
        return opinion


def get_opinion_counts(node: Node) -> dict[str, int]:
    qs = Opinion.objects.filter(node=node).values("opinion_type").annotate(count=Count("id"))
    return {row["opinion_type"]: row["count"] for row in qs}


def get_participant_opinion_type(*, participant: SpaceParticipant, node: Node) -> str | None:
    opinion = Opinion.objects.filter(participant=participant, node=node).values_list("opinion_type", flat=True).first()
    return opinion


def get_opinion_counts_batch(node_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    qs = Opinion.objects.filter(node_id__in=node_ids).values("node_id", "opinion_type").annotate(count=Count("id"))
    result: dict[uuid.UUID, dict[str, int]] = {}
    for row in qs:
        result.setdefault(row["node_id"], {})[row["opinion_type"]] = row["count"]
    return result


def toggle_reaction(
    *,
    participant: SpaceParticipant,
    post: Node,
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
        SpaceParticipant.objects.select_for_update().get(pk=participant.pk)
        existing = Reaction.objects.select_for_update().filter(participant=participant, post=post).first()
        if existing:
            if existing.reaction_type == reaction_type:
                existing.delete()
                Space.objects.filter(pk=space.pk).update(updated_at=timezone.now())
                return None
            existing.reaction_type = reaction_type
            existing.save(update_fields=["reaction_type"])
            Space.objects.filter(pk=space.pk).update(updated_at=timezone.now())
            return existing

        reaction = Reaction.objects.create(
            participant=participant,
            post=post,
            reaction_type=reaction_type,
        )
        Space.objects.filter(pk=space.pk).update(updated_at=timezone.now())
        return reaction


def get_participant_reactions_batch(
    *, participant: SpaceParticipant, post_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Return a mapping of post_id → reaction_type for the given participant."""
    qs = Reaction.objects.filter(participant=participant, post_id__in=post_ids).values_list("post_id", "reaction_type")
    return dict(qs)


def get_reaction_counts_batch(post_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    """Return a mapping of post_id → {reaction_type → count} for the given posts."""
    qs = Reaction.objects.filter(post_id__in=post_ids).values("post_id", "reaction_type").annotate(count=Count("id"))
    result: dict[uuid.UUID, dict[str, int]] = {}
    for row in qs:
        result.setdefault(row["post_id"], {})[row["reaction_type"]] = row["count"]
    return result
