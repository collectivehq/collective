from __future__ import annotations

from apps.core.templatetags.core_tags import sanitize_html


def test_sanitize_html_removes_unsafe_tags() -> None:
    cleaned = sanitize_html('<p>Safe</p><script>alert("x")</script>')

    assert cleaned == "<p>Safe</p>"


def test_sanitize_html_keeps_supported_markup() -> None:
    cleaned = sanitize_html('<p><a href="https://example.com">Link</a></p>')

    assert cleaned == '<p><a href="https://example.com" rel="noopener noreferrer">Link</a></p>'
