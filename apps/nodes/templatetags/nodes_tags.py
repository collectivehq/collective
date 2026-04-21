from __future__ import annotations

from datetime import timedelta

import nh3
from django import template
from django.utils.safestring import mark_safe

from apps.nodes.models import Node

register = template.Library()


@register.filter
def is_edited(post: Node) -> bool:
    """Check if a post has been edited (updated_at > created_at + 1 second)."""
    if post.is_draft:
        return False
    if not post.updated_at or not post.created_at:
        return False
    return (post.updated_at - post.created_at) > timedelta(seconds=1)


@register.filter
def sanitize_html(value: str | None) -> str:
    """Sanitize HTML content, allowing safe tags from the rich text editor."""
    if not value:
        return ""
    clean = nh3.clean(
        str(value),
        tags={
            "a",
            "b",
            "blockquote",
            "br",
            "code",
            "del",
            "div",
            "em",
            "figcaption",
            "figure",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "i",
            "img",
            "li",
            "ol",
            "p",
            "pre",
            "span",
            "strong",
            "sub",
            "sup",
            "table",
            "tbody",
            "td",
            "th",
            "thead",
            "tr",
            "ul",
        },
        attributes={
            "a": {"href", "target"},
            "img": {"src", "alt", "width", "height"},
            "span": {"style"},
            "td": {"colspan", "rowspan", "style"},
            "th": {"colspan", "rowspan", "style"},
            "*": {"class"},
        },
        link_rel="noopener noreferrer",
        url_schemes={"http", "https", "mailto"},
    )
    return mark_safe(clean)  # noqa: S308


@register.filter
def get_role(role_map: dict[object, str] | None, user_id: object) -> str:
    """Look up a user's role label from the role map."""
    if not role_map:
        return ""
    return role_map.get(user_id, "")


_RESOLUTION_LABELS: dict[str, str] = {
    "accept": "Accepted",
    "reject": "Rejected",
    "close": "Closed",
}


@register.filter
def resolution_label(value: str) -> str:
    """Convert resolution type to past-tense display label."""
    return _RESOLUTION_LABELS.get(value, value)


@register.inclusion_tag("nodes/_resolution_icon.html")
def resolution_icon(resolution_value: str, size: str = "w-3.5 h-3.5") -> dict[str, str]:
    """Render an icon for a resolution type (accept/reject/close)."""
    return {"resolution_value": resolution_value, "size": size}
