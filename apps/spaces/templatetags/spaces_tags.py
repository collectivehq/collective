from __future__ import annotations

from django import template

from apps.spaces.models import Space

register = template.Library()

_LIFECYCLE_BADGE: dict[str, str] = {
    "open": "badge-success",
    "draft": "badge-outline",
    "closed": "badge-warning",
    "archived": "badge-neutral",
}


@register.inclusion_tag("spaces/_lifecycle_badge.html")
def lifecycle_badge(space: Space) -> dict[str, str]:
    return {
        "badge_class": _LIFECYCLE_BADGE.get(space.lifecycle, "badge-outline"),
        "label": space.get_lifecycle_display(),
    }
