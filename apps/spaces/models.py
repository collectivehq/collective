from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from apps.core.models import BaseModel, CRUDModel
from apps.spaces.constants import VALID_OPINION_TYPES, VALID_REACTION_TYPES
from apps.spaces.querysets import SpaceQuerySet


def validate_opinion_types(value: list[str]) -> None:
    invalid = set(value) - VALID_OPINION_TYPES
    if invalid:
        raise ValidationError(f"Invalid opinion types: {invalid}. Must be a subset of {set(VALID_OPINION_TYPES)}.")


def validate_reaction_types(value: list[str]) -> None:
    invalid = set(value) - VALID_REACTION_TYPES
    if invalid:
        raise ValidationError(f"Invalid reaction types: {invalid}. Must be a subset of {set(VALID_REACTION_TYPES)}.")


class Space(CRUDModel):
    class Lifecycle(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        ARCHIVED = "archived", "Archived"

    class ReactionType(models.TextChoices):
        LIKE = "like", "Like"
        DISLIKE = "dislike", "Dislike"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    information = models.TextField(blank=True, default="")
    root_discussion = models.OneToOneField(
        "discussions.Discussion",
        on_delete=models.PROTECT,
        related_name="root_of_space",
        null=True,
        blank=True,
    )
    lifecycle = models.CharField(max_length=20, choices=Lifecycle.choices, default=Lifecycle.DRAFT)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Public spaces are listed and can be joined directly. Private spaces require invites.",
    )
    opinion_types = ArrayField(
        models.CharField(max_length=20),
        default=list,
        blank=True,
        validators=[validate_opinion_types],
        help_text='Subset of ["agree", "abstain", "disagree"]',
    )
    reaction_types = ArrayField(
        models.CharField(max_length=20),
        default=list,
        blank=True,
        validators=[validate_reaction_types],
        help_text='Subset of ["like", "dislike"]',
    )
    edit_window_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=None,
        help_text="Minutes after posting during which edits are allowed. None = no limit, 0 = disabled.",
    )
    default_role = models.ForeignKey(
        "spaces.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_spaces",
    )
    template_slug = models.CharField(max_length=100, blank=True, default="")

    objects = SpaceQuerySet.as_manager()

    class Meta:
        db_table = "spaces"
        ordering = ["-updated_at", "-created_at"]
        verbose_name = "space"
        verbose_name_plural = "spaces"
        indexes = [
            models.Index(fields=["lifecycle"], name="spaces_lifecycle_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if self.default_role_id is not None and self.default_role is not None and self.default_role.space_id != self.pk:
            raise ValidationError({"default_role": "Default role must belong to this space."})

    @property
    def is_active(self) -> bool:
        if self.lifecycle != self.Lifecycle.OPEN or self.deleted_at is not None:
            return False
        now = timezone.now()
        if self.ends_at and now >= self.ends_at:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        return True


class Role(BaseModel):
    hex_color_validator = RegexValidator(
        regex=r"^#[0-9A-Fa-f]{6}$",
        message="Enter a valid hex color like #A1B2C3.",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("spaces.Space", on_delete=models.CASCADE, related_name="roles")
    label = models.CharField(max_length=100)
    post_highlight_color = models.CharField(max_length=7, blank=True, default="", validators=[hex_color_validator])
    can_post = models.BooleanField(default=True)
    can_create_draft = models.BooleanField(default=True)
    can_edit_others_post = models.BooleanField(default=False)
    can_delete_own_post = models.BooleanField(default=True)
    can_view_history = models.BooleanField(default=True)
    can_create_discussion = models.BooleanField(default=False)
    can_rename_discussion = models.BooleanField(default=False)
    can_delete_discussion = models.BooleanField(default=False)
    can_promote_post = models.BooleanField(default=False)
    can_set_permissions = models.BooleanField(default=False)
    can_resolve = models.BooleanField(default=False)
    can_reopen_discussion = models.BooleanField(default=False)
    can_reorganise = models.BooleanField(default=False)
    can_restructure = models.BooleanField(default=False)
    can_moderate_content = models.BooleanField(default=False)
    can_manage_participants = models.BooleanField(default=False)
    can_close_space = models.BooleanField(default=False)
    can_archive_space = models.BooleanField(default=False)
    can_unarchive_space = models.BooleanField(default=False)
    can_modify_closed_space = models.BooleanField(default=False)
    can_view_drafts = models.BooleanField(default=False)
    can_opine = models.BooleanField(default=True)
    can_react = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "roles"
        verbose_name = "role"
        verbose_name_plural = "roles"
        constraints = [
            UniqueConstraint(fields=["space", "label"], name="roles_space_label_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.space.title})"


class SpaceParticipant(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("spaces.Space", on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participations")
    role = models.ForeignKey("spaces.Role", on_delete=models.PROTECT, related_name="participants")

    class Meta:
        db_table = "space_participants"
        verbose_name = "space participant"
        verbose_name_plural = "space participants"
        constraints = [
            UniqueConstraint(fields=["space", "user"], name="space_participants_space_user_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.space}"

    def clean(self) -> None:
        super().clean()
        if self.role_id is not None and self.role is not None and self.role.space_id != self.space_id:
            raise ValidationError({"role": "Role must belong to the participant's space."})
