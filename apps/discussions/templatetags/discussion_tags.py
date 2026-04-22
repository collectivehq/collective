from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_RESOLUTION_LABELS = {
    "accept": "Accepted",
    "reject": "Rejected",
    "close": "Closed",
}

_RESOLUTION_ICON_HTML = {
    "accept": '<span class="text-success" title="Accepted"><i data-lucide="check-circle" class="w-3 h-3"></i></span>',
    "reject": '<span class="text-error" title="Rejected"><i data-lucide="x-circle" class="w-3 h-3"></i></span>',
    "close": '<span class="text-warning" title="Closed"><i data-lucide="minus-circle" class="w-3 h-3"></i></span>',
}


@register.filter
def resolution_label(value: str) -> str:
    return _RESOLUTION_LABELS.get(value, "")


@register.simple_tag
def resolution_icon(value: str) -> str:
    return mark_safe(_RESOLUTION_ICON_HTML.get(value, ""))  # noqa: S308
