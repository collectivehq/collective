from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from django.utils.html import escape
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from apps.spaces.import_support import (
    ImportedDiscussion,
    build_imported_discussions,
    materialize_imported_discussions,
    normalize_import_label,
)
from apps.spaces.models import Space
from apps.users.models import User

_BULLET_PREFIX_RE = re.compile(r"^(?P<indent>\s*)[-*•]\s+")
_STYLE_LEVEL_RE = re.compile(r"(\d+)$")


class DocxImportError(ValueError):
    pass


def _strip_bullet_prefix(text: str) -> str:
    return _BULLET_PREFIX_RE.sub("", text).strip()


def _paragraph_level(paragraph: Any) -> int:
    ilvl = paragraph._p.xpath("./w:pPr/w:numPr/w:ilvl/@w:val")
    if ilvl:
        return int(ilvl[0])

    style_name = getattr(getattr(paragraph, "style", None), "name", "") or ""
    match = _STYLE_LEVEL_RE.search(style_name)
    if style_name.startswith("List") and match:
        return max(int(match.group(1)) - 1, 0)

    left_indent = getattr(getattr(paragraph, "paragraph_format", None), "left_indent", None)
    if left_indent is not None:
        return max(int(round(left_indent.pt / 18.0)), 0)

    text = paragraph.text or ""
    bullet_match = _BULLET_PREFIX_RE.match(text)
    if bullet_match:
        return len(bullet_match.group("indent")) // 2

    return 0


def _content_blocks_to_html(blocks: list[str]) -> str:
    paragraphs = [f"<p>{escape(block)}</p>" for block in blocks if block]
    return "".join(paragraphs)


def _parse_content(paragraphs: list[Any]) -> dict[str, str]:
    content_by_label: dict[str, list[str]] = {}
    current_key: str | None = None

    for paragraph in paragraphs:
        text = " ".join((paragraph.text or "").split())
        if not text:
            continue

        style_name = getattr(getattr(paragraph, "style", None), "name", "") or ""
        if style_name.startswith("Heading"):
            current_key = normalize_import_label(text)
            if current_key in content_by_label:
                raise DocxImportError(f'Duplicate content heading "{text}" in DOCX import.')
            content_by_label[current_key] = []
            continue

        if current_key is not None:
            content_by_label[current_key].append(text)

    return {key: _content_blocks_to_html(blocks) for key, blocks in content_by_label.items()}


def parse_space_docx(*, docx_bytes: bytes) -> list[ImportedDiscussion]:
    try:
        document = Document(BytesIO(docx_bytes))
    except (PackageNotFoundError, ValueError, KeyError) as exc:
        raise DocxImportError("Could not read the DOCX file.") from exc

    mode: str | None = None
    structure_entries: list[tuple[int, str]] = []
    content_paragraphs: list[Any] = []
    seen_structure_labels: set[str] = set()

    for paragraph in document.paragraphs:
        raw_text = paragraph.text or ""
        text = " ".join(raw_text.split())
        if not text:
            continue

        normalized = normalize_import_label(text)
        if normalized == "structure":
            mode = "structure"
            continue
        if normalized == "content":
            mode = "content"
            continue

        if mode == "structure":
            label = _strip_bullet_prefix(raw_text)
            key = normalize_import_label(label)
            if not label:
                continue
            if key in seen_structure_labels:
                raise DocxImportError(f'Duplicate structure label "{label}" in DOCX import.')
            seen_structure_labels.add(key)
            structure_entries.append((_paragraph_level(paragraph), label))
        elif mode == "content":
            content_paragraphs.append(paragraph)

    content_by_label = _parse_content(content_paragraphs)
    return build_imported_discussions(
        structure_entries=structure_entries,
        content_by_label=content_by_label,
        error_cls=DocxImportError,
        source_name="DOCX",
    )


def import_space_from_docx(*, space: Space, author: User, docx_bytes: bytes) -> None:
    materialize_imported_discussions(
        space=space,
        author=author,
        discussions=parse_space_docx(docx_bytes=docx_bytes),
        error_cls=DocxImportError,
    )
