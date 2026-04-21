from __future__ import annotations

import re

import markdown as markdown_lib  # type: ignore[import-untyped]

from apps.spaces.import_support import (
    ImportedDiscussion,
    build_imported_discussions,
    materialize_imported_discussions,
    normalize_import_label,
)
from apps.spaces.models import Space
from apps.users.models import User

_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<text>.+?)\s*$")
_STRUCTURE_ITEM_RE = re.compile(r"^(?P<indent>\s*)[-*+]\s+(?P<label>.+\S)\s*$")


class MarkdownImportError(ValueError):
    pass


def _content_markdown_to_html(lines: list[str]) -> str:
    source = "\n".join(lines).strip()
    if not source:
        return ""
    return str(markdown_lib.markdown(source, extensions=["extra"]))


def _parse_content(lines: list[str]) -> dict[str, str]:
    content_by_label: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        if current_key is None:
            return
        content_by_label[current_key] = _content_markdown_to_html(current_lines)

    for raw_line in lines:
        heading_match = _HEADING_RE.match(raw_line)
        if heading_match:
            flush_current()
            heading_text = heading_match.group("text")
            current_key = normalize_import_label(heading_text)
            if current_key in content_by_label:
                raise MarkdownImportError(f'Duplicate content heading "{heading_text}" in Markdown import.')
            current_lines = []
            continue

        if current_key is not None:
            current_lines.append(raw_line)

    flush_current()
    return content_by_label


def parse_space_markdown(*, markdown_bytes: bytes) -> list[ImportedDiscussion]:
    try:
        text = markdown_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarkdownImportError("Markdown import requires a UTF-8 encoded file.") from exc

    mode: str | None = None
    structure_entries: list[tuple[int, str]] = []
    content_lines: list[str] = []
    seen_structure_labels: set[str] = set()

    for raw_line in text.splitlines():
        heading_match = _HEADING_RE.match(raw_line)
        if heading_match:
            normalized_heading = normalize_import_label(heading_match.group("text"))
            if normalized_heading == "structure":
                mode = "structure"
                continue
            if normalized_heading == "content":
                mode = "content"
                continue

        if mode == "structure":
            if not raw_line.strip():
                continue
            item_match = _STRUCTURE_ITEM_RE.match(raw_line)
            if item_match is None:
                raise MarkdownImportError("Structure section must use markdown bullet list items.")
            label = item_match.group("label").strip()
            key = normalize_import_label(label)
            if key in seen_structure_labels:
                raise MarkdownImportError(f'Duplicate structure label "{label}" in Markdown import.')
            seen_structure_labels.add(key)
            indent = len(item_match.group("indent").expandtabs(2))
            if indent % 2 != 0:
                raise MarkdownImportError(
                    f'Structure item "{label}" uses unsupported indentation. Use multiples of two spaces.'
                )
            structure_entries.append((indent // 2, label))
        elif mode == "content":
            content_lines.append(raw_line)

    return build_imported_discussions(
        structure_entries=structure_entries,
        content_by_label=_parse_content(content_lines),
        error_cls=MarkdownImportError,
        source_name="Markdown",
    )


def import_space_from_markdown(*, space: Space, author: User, markdown_bytes: bytes) -> None:
    materialize_imported_discussions(
        space=space,
        author=author,
        discussions=parse_space_markdown(markdown_bytes=markdown_bytes),
        error_cls=MarkdownImportError,
    )
