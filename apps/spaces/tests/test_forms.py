from __future__ import annotations

import pytest

from apps.spaces.forms import SpaceSettingsForm
from apps.spaces.tests.factories import SpaceFactory


@pytest.mark.django_db
class TestSpaceSettingsForm:
    def test_rejects_edit_window_minutes_outside_allowed_steps(self):
        space = SpaceFactory()
        form = SpaceSettingsForm(
            data={
                "title": space.title,
                "description": space.description,
                "information": space.information,
                "lifecycle": space.lifecycle,
                "starts_at": "",
                "ends_at": "",
                "opinion_types": list(space.opinion_types),
                "reaction_types": list(space.reaction_types),
                "edit_window_minutes": "7",
            },
            instance=space,
        )

        assert form.is_valid() is False
        assert form.errors["edit_window_minutes"] == ["Select a valid edit window."]

    def test_accepts_configured_edit_window_minutes_step(self):
        space = SpaceFactory()
        form = SpaceSettingsForm(
            data={
                "title": space.title,
                "description": space.description,
                "information": space.information,
                "lifecycle": space.lifecycle,
                "starts_at": "",
                "ends_at": "",
                "opinion_types": list(space.opinion_types),
                "reaction_types": list(space.reaction_types),
                "edit_window_minutes": "60",
            },
            instance=space,
        )

        assert form.is_valid() is True
        assert form.cleaned_data["edit_window_minutes"] == 60
