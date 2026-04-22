from __future__ import annotations

from typing import Any, cast

import filetype
from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.urls import reverse

from apps.spaces.constants import EDIT_WINDOW_STEPS, MAX_IMPORT_FILE_SIZE, OPINION_TYPE_CHOICES, REACTION_TYPE_CHOICES
from apps.spaces.models import Space

# DOCX files are ZIP-based (OOXML); filetype returns 'application/zip'.
_DOCX_MIME = "application/zip"
# Plain text has no reliable magic bytes; rely on extension + size for markdown.
_MARKDOWN_EXTENSIONS = (".md", ".markdown")


class SpaceCreateForm(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea, required=False)
    information = forms.CharField(
        widget=forms.Textarea(attrs={"class": "textarea tinymce-editor w-full", "rows": 8}),
        required=False,
    )
    source_docx = forms.FileField(required=False)
    source_markdown = forms.FileField(required=False)

    def clean_source_docx(self) -> UploadedFile | None:
        uploaded = cast(UploadedFile | None, self.cleaned_data.get("source_docx"))
        if uploaded is None:
            return None
        uploaded_name = uploaded.name or ""
        if not uploaded_name.lower().endswith(".docx"):
            raise forms.ValidationError("Upload a DOCX file.")
        uploaded_size = uploaded.size
        if uploaded_size is None or uploaded_size > MAX_IMPORT_FILE_SIZE:
            raise forms.ValidationError("DOCX file is too large (max 5MB).")
        # Validate magic bytes — DOCX is ZIP-based (OOXML).
        header = uploaded.read(261)
        uploaded.seek(0)
        kind = filetype.guess(header)
        if kind is None or kind.mime != _DOCX_MIME:
            raise forms.ValidationError("Uploaded file does not appear to be a valid DOCX file.")
        return uploaded

    def clean_source_markdown(self) -> UploadedFile | None:
        uploaded = cast(UploadedFile | None, self.cleaned_data.get("source_markdown"))
        if uploaded is None:
            return None
        uploaded_name = uploaded.name or ""
        if not uploaded_name.lower().endswith(_MARKDOWN_EXTENSIONS):
            raise forms.ValidationError("Upload a Markdown file.")
        uploaded_size = uploaded.size
        if uploaded_size is None or uploaded_size > MAX_IMPORT_FILE_SIZE:
            raise forms.ValidationError("Markdown file is too large (max 5MB).")
        # Markdown is plain text — no reliable magic bytes.  Reject if filetype
        # detects a binary format (e.g. uploaded a PDF disguised as .md).
        header = uploaded.read(261)
        uploaded.seek(0)
        kind = filetype.guess(header)
        if kind is not None:
            raise forms.ValidationError("Uploaded file does not appear to be a plain-text Markdown file.")
        return uploaded

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean() or {}
        if cleaned_data.get("source_docx") and cleaned_data.get("source_markdown"):
            raise forms.ValidationError("Upload either a DOCX file or a Markdown file, not both.")
        return cleaned_data


class SpaceSettingsForm(forms.ModelForm):  # type: ignore[type-arg]
    opinion_types = forms.MultipleChoiceField(
        choices=OPINION_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-sm"}),
        required=False,
    )
    reaction_types = forms.MultipleChoiceField(
        choices=REACTION_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-sm"}),
        required=False,
    )

    class Meta:
        model = Space
        fields = [
            "title",
            "description",
            "information",
            "lifecycle",
            "starts_at",
            "ends_at",
            "opinion_types",
            "reaction_types",
            "edit_window_minutes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input w-full"}),
            "description": forms.Textarea(attrs={"class": "textarea w-full", "rows": 4}),
            "information": forms.Textarea(attrs={"class": "textarea tinymce-editor w-full", "rows": 8}),
            "lifecycle": forms.Select(attrs={"class": "select w-full"}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input w-full"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input w-full"}),
            "edit_window_minutes": forms.HiddenInput(attrs={"x-ref": "hidden"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["information"].widget.attrs["data-upload-url"] = reverse(
                "posts:image_upload", kwargs={"space_id": self.instance.pk}
            )

    VALID_TRANSITIONS: dict[str, set[str]] = {
        "draft": {"open"},
        "open": {"closed"},
        "closed": {"open", "archived"},
        "archived": set(),
    }

    def clean_lifecycle(self) -> str:
        new = str(self.cleaned_data["lifecycle"])
        if self.instance.pk:
            old = self.instance.lifecycle
            if new != old and new not in self.VALID_TRANSITIONS.get(old, set()):
                raise forms.ValidationError(f"Cannot transition from '{old}' to '{new}'.")
        return new

    def clean_edit_window_minutes(self) -> int | None:
        edit_window_minutes = self.cleaned_data.get("edit_window_minutes")
        if edit_window_minutes not in EDIT_WINDOW_STEPS:
            raise forms.ValidationError("Select a valid edit window.")
        return edit_window_minutes
