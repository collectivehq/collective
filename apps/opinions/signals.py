from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.dispatch import receiver

from apps.nodes.signals import nodes_soft_deleted
from apps.opinions.models import Opinion, Reaction


@receiver(nodes_soft_deleted)
def delete_feedback_for_soft_deleted_nodes(*, node_ids: Sequence[object], **kwargs: Any) -> None:
    Opinion.objects.filter(node_id__in=node_ids).delete()
    Reaction.objects.filter(post_id__in=node_ids).delete()
