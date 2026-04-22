from __future__ import annotations

from collections.abc import Sequence

from django.dispatch import receiver

from apps.discussions.signals import discussion_items_soft_deleted
from apps.reactions.models import Reaction


@receiver(discussion_items_soft_deleted)
def delete_reactions_for_soft_deleted_discussion_items(*, item_ids: Sequence[object], **kwargs: object) -> None:
    Reaction.objects.filter(post_id__in=item_ids).delete()
