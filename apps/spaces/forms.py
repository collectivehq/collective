from __future__ import annotations

from django import forms

from apps.spaces.models import Space

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
            "lifecycle",
            "starts_at",
            "ends_at",
            "opinion_types",
            "reaction_types",
            "edit_window_minutes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 4}),
            "lifecycle": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input input-bordered w-full"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input input-bordered w-full"}),
            "edit_window_minutes": forms.HiddenInput(attrs={"x-ref": "hidden"}),
        }

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
