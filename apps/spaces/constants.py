from __future__ import annotations

VALID_OPINION_TYPES: frozenset[str] = frozenset({"agree", "abstain", "disagree"})
VALID_REACTION_TYPES: frozenset[str] = frozenset({"like", "dislike"})

EDIT_WINDOW_STEP_OPTIONS: list[tuple[int | None, str, str]] = [
    (0, "Disabled", "Off"),
    (5, "5 min", "5m"),
    (10, "10 min", "10m"),
    (30, "30 min", "30m"),
    (60, "1 hour", "1h"),
    (1440, "1 day", "1d"),
    (None, "No limit", "∞"),
]

EDIT_WINDOW_STEPS: list[int | None] = [step for step, _, _ in EDIT_WINDOW_STEP_OPTIONS]

OPINION_TYPE_CHOICES: list[tuple[str, str]] = [
    ("agree", "Agree"),
    ("abstain", "Abstain"),
    ("disagree", "Disagree"),
]

REACTION_TYPE_CHOICES: list[tuple[str, str]] = [
    ("like", "Like"),
    ("dislike", "Dislike"),
]

POST_HIGHLIGHT_COLOR_PRESETS: list[tuple[str, str]] = [
    ("Amber", "#FDE68A"),
    ("Rose", "#FDA4AF"),
    ("Sky", "#93C5FD"),
    ("Mint", "#86EFAC"),
    ("Lavender", "#C4B5FD"),
    ("Slate", "#CBD5E1"),
]

MAX_IMPORT_FILE_SIZE: int = 5 * 1024 * 1024  # 5 MB

# Order matters: this mapping defines the UI display order for role permissions.
PERMISSION_LABELS: dict[str, str] = {
    # Participation
    "can_post": "Post messages",
    "can_create_draft": "Save draft posts",
    "can_edit_others_post": "Edit others' posts",
    "can_delete_own_post": "Delete own posts",
    "can_view_drafts": "View draft posts",
    "can_view_history": "View edit history",
    "can_opine": "Express opinions",
    "can_react": "React to posts",
    # Discussion structure
    "can_create_discussion": "Create discussions",
    "can_rename_discussion": "Rename discussions",
    "can_delete_discussion": "Delete discussions",
    "can_promote_post": "Promote posts to discussions",
    # Resolution
    "can_resolve": "Resolve discussions",
    "can_reopen_discussion": "Reopen discussions",
    # Reorganisation
    "can_reorganise": "Move and reorder posts",
    "can_restructure": "Merge and split discussions",
    # Moderation
    "can_moderate_content": "Delete any post or link",
    "can_manage_participants": "Manage participants and invites",
    # Administration
    "can_set_permissions": "Manage roles and permissions",
    "can_close_space": "Close or reopen space",
    "can_archive_space": "Archive space",
    "can_unarchive_space": "Unarchive space",
    "can_modify_closed_space": "Modify closed spaces",
}

PERMISSION_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Participation",
        (
            "can_post",
            "can_create_draft",
            "can_edit_others_post",
            "can_delete_own_post",
            "can_view_drafts",
            "can_view_history",
            "can_opine",
            "can_react",
        ),
    ),
    (
        "Discussion Structure",
        (
            "can_create_discussion",
            "can_rename_discussion",
            "can_delete_discussion",
            "can_promote_post",
        ),
    ),
    (
        "Resolution",
        (
            "can_resolve",
            "can_reopen_discussion",
        ),
    ),
    (
        "Reorganisation",
        (
            "can_reorganise",
            "can_restructure",
        ),
    ),
    (
        "Moderation",
        (
            "can_moderate_content",
            "can_manage_participants",
        ),
    ),
    (
        "Administration",
        (
            "can_set_permissions",
            "can_close_space",
            "can_archive_space",
            "can_unarchive_space",
            "can_modify_closed_space",
        ),
    ),
)
