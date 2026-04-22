from __future__ import annotations

VALID_OPINION_TYPES: frozenset[str] = frozenset({"agree", "abstain", "disagree"})
VALID_REACTION_TYPES: frozenset[str] = frozenset({"like", "dislike"})

OPINION_TYPE_CHOICES: list[tuple[str, str]] = [
    ("agree", "Agree"),
    ("abstain", "Abstain"),
    ("disagree", "Disagree"),
]

REACTION_TYPE_CHOICES: list[tuple[str, str]] = [
    ("like", "Like"),
    ("dislike", "Dislike"),
]

MAX_IMPORT_FILE_SIZE: int = 5 * 1024 * 1024  # 5 MB

PERMISSION_LABELS: dict[str, str] = {
    "can_post": "Post messages",
    "can_view_drafts": "View draft posts",
    "can_opine": "Express opinions",
    "can_react": "React to posts",
    "can_shape_tree": "Shape discussion tree",
    "can_resolve": "Resolve discussions",
    "can_reorganise": "Reorganise content",
    "can_moderate": "Moderate participants",
    "can_set_permissions": "Manage permissions",
    "can_close_space": "Close / archive space",
}
