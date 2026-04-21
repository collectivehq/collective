from __future__ import annotations

from django import template
from django.db.models import QuerySet

from apps.opinions.models import Reaction

register = template.Library()


@register.filter
def filter_reactions_by_type(queryset: QuerySet[Reaction] | list[Reaction], type_value: str) -> list[Reaction]:
    return [item for item in queryset if item.reaction_type == type_value]


@register.filter
def dict_get(dictionary: dict[str, int] | None, key: str) -> int:
    if dictionary is None:
        return 0
    return dictionary.get(key, 0)
