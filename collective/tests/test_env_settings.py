from __future__ import annotations

import pytest
from collective.settings.env import env_list


class TestEnvList:
    def test_discards_blank_entries_and_trims_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", " example.com, , api.example.com ,, ")

        assert env_list("DJANGO_ALLOWED_HOSTS") == ["example.com", "api.example.com"]
