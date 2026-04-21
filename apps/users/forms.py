from __future__ import annotations

from django import forms

from apps.users.models import User


class ProfileForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = User
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(attrs={"class": "input w-full", "placeholder": "Display name"}),
        }
