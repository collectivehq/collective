from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


@pytest.fixture
def open_space():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    return Space.objects.get(pk=space.pk)


@pytest.mark.django_db
class TestSpaceIsActive:
    def test_open_space_true(self, open_space):
        assert open_space.is_active is True

    def test_draft_space_false(self, open_space):
        open_space.lifecycle = Space.Lifecycle.DRAFT
        open_space.save()
        assert open_space.is_active is False

    def test_closed_space_false(self, open_space):
        open_space.lifecycle = Space.Lifecycle.CLOSED
        open_space.save(update_fields=["lifecycle"])
        assert open_space.is_active is False

    def test_archived_space_false(self, open_space):
        open_space.lifecycle = Space.Lifecycle.ARCHIVED
        open_space.save(update_fields=["lifecycle"])
        assert open_space.is_active is False

    def test_not_started_false(self, open_space):
        open_space.starts_at = timezone.now() + datetime.timedelta(hours=1)
        open_space.save()
        assert open_space.is_active is False

    def test_started_true(self, open_space):
        open_space.starts_at = timezone.now() - datetime.timedelta(hours=1)
        open_space.save()
        assert open_space.is_active is True

    def test_not_ended_true(self, open_space):
        open_space.ends_at = timezone.now() + datetime.timedelta(hours=1)
        open_space.save()
        assert open_space.is_active is True

    def test_ended_false(self, open_space):
        open_space.ends_at = timezone.now() - datetime.timedelta(hours=1)
        open_space.save()
        assert open_space.is_active is False
