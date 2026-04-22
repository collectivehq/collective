from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from apps.discussions import services as discussion_services
from apps.discussions.models import Discussion
from apps.posts import services as post_services
from apps.spaces.models import Space
from apps.users.models import User


@dataclass(slots=True)
class ImportedDiscussion:
    label: str
    content_html: str = ""
    children: list[ImportedDiscussion] = field(default_factory=list)


def normalize_import_label(value: str) -> str:
    return " ".join(value.split()).casefold()


def build_imported_discussions(
    *,
    structure_entries: list[tuple[int, str]],
    content_by_label: Mapping[str, str],
    error_cls: type[ValueError],
    source_name: str,
) -> list[ImportedDiscussion]:
    if not structure_entries:
        raise error_cls(f'{source_name} import requires a "Structure" section with at least one item.')

    structure_labels = {normalize_import_label(label) for _, label in structure_entries}
    unknown_content = sorted(label for label in content_by_label if label not in structure_labels)
    if unknown_content:
        unknown_labels = ", ".join(unknown_content)
        raise error_cls(f"Content section references unknown structure items: {unknown_labels}.")

    roots: list[ImportedDiscussion] = []
    stack: list[tuple[int, ImportedDiscussion]] = []

    for level, label in structure_entries:
        if not stack and level > 0:
            raise error_cls("Structure section cannot start with an indented item.")

        while stack and stack[-1][0] >= level:
            stack.pop()

        if level > 0 and not stack:
            raise error_cls(f'Structure item "{label}" is missing a parent item.')

        discussion = ImportedDiscussion(
            label=label, content_html=content_by_label.get(normalize_import_label(label), "")
        )
        if stack:
            stack[-1][1].children.append(discussion)
        else:
            roots.append(discussion)
        stack.append((level, discussion))

    return roots


def _materialize_discussion(*, parent: Discussion, space: Space, author: User, discussion: ImportedDiscussion) -> None:
    created = discussion_services.create_child_discussion(parent=parent, space=space, label=discussion.label)
    if discussion.content_html:
        post_services.create_post(discussion=created, author=author, content=discussion.content_html)
    for child in discussion.children:
        _materialize_discussion(parent=created, space=space, author=author, discussion=child)


def materialize_imported_discussions(
    *,
    space: Space,
    author: User,
    discussions: list[ImportedDiscussion],
    error_cls: type[ValueError],
) -> None:
    if space.root_discussion is None:
        raise error_cls("Space root discussion is not initialized.")

    for discussion in discussions:
        _materialize_discussion(parent=space.root_discussion, space=space, author=author, discussion=discussion)
