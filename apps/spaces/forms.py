from __future__ import annotations

from typing import Any

from django import forms
from django.urls import reverse

from apps.spaces.models import Space

MAX_IMPORT_FILE_SIZE = 5 * 1024 * 1024

OPINION_TYPE_CHOICES = [
    ("agree", "Agree"),
    ("abstain", "Abstain"),
    ("disagree", "Disagree"),
]

REACTION_TYPE_CHOICES = [
    ("like", "Like"),
    ("dislike", "Dislike"),
]


class SpaceCreateForm(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea, required=False)
    information = forms.CharField(
        widget=forms.Textarea(attrs={"class": "textarea tinymce-editor w-full", "rows": 8}),
        required=False,
    )
    source_docx = forms.FileField(required=False)
    source_markdown = forms.FileField(required=False)

    def clean_source_docx(self) -> Any:
        uploaded = self.cleaned_data.get("source_docx")
        if uploaded is None:
            return None
        if not uploaded.name.lower().endswith(".docx"):
            raise forms.ValidationError("Upload a DOCX file.")
        if uploaded.size > MAX_IMPORT_FILE_SIZE:
            raise forms.ValidationError("DOCX file is too large (max 5MB).")
        return uploaded

    def clean_source_markdown(self) -> Any:
        uploaded = self.cleaned_data.get("source_markdown")
        if uploaded is None:
            return None
        if not uploaded.name.lower().endswith((".md", ".markdown")):
            raise forms.ValidationError("Upload a Markdown file.")
        if uploaded.size > MAX_IMPORT_FILE_SIZE:
            raise forms.ValidationError("Markdown file is too large (max 5MB).")
        return uploaded

    def clean(self) -> dict[str, Any]:
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
                "nodes:image_upload", kwargs={"space_id": self.instance.pk}
            )

    VALID_TRANSITIONS: dict[str, set[str]] = {
        "draft": {"open"},
        "open": {"closed"},
        "closed": {"open", "archived"},
        "archived": set(),
    }

    def clean_lifecycle(self) -> str:
        new = self.cleaned_data["lifecycle"]
        if self.instance.pk:
            old = self.instance.lifecycle
            if new != old and new not in self.VALID_TRANSITIONS.get(old, set()):
                raise forms.ValidationError(f"Cannot transition from '{old}' to '{new}'.")
        return new  # type: ignore[no-any-return]
