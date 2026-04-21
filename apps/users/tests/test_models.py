from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.users.models import User
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestUser:
    def test_create_user(self):
        user = UserFactory(name="Alice", email="alice@example.com")
        assert user.pk is not None
        assert user.name == "Alice"
        assert user.email == "alice@example.com"

    def test_str_with_name(self):
        user = UserFactory(name="Bob")
        assert str(user) == "Bob"

    def test_str_without_name(self):
        user = UserFactory(name="", email="noname@example.com")
        assert str(user) == "noname@example.com"

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == "email"

    def test_uuid_primary_key(self):
        user = UserFactory()
        assert user.pk is not None
        assert len(str(user.pk)) == 36  # UUID format

    def test_tags_default_empty(self):
        user = UserFactory()
        assert user.tags == []

    def test_unique_email(self):
        UserFactory(email="unique@example.com")
        with pytest.raises(IntegrityError):
            UserFactory(email="unique@example.com")
