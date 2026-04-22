from __future__ import annotations

import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def sanitize_html(value: str | None) -> str:
    """Sanitize rich-text HTML while preserving the supported editor markup."""
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
    if not role_map or user_id is None:
        return ""
    return role_map.get(user_id, "")


@register.filter
def dict_get(dictionary: dict[str, int] | None, key: str) -> int:
    if dictionary is None:
        return 0
    return dictionary.get(key, 0)
