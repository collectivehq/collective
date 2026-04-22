from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.discussions.tests.factories import DiscussionFactory
from apps.opinions.models import Opinion
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestOpinion:
    def test_create_opinion(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        opinion = Opinion.objects.create(created_by=user, discussion=discussion, opinion_type=Opinion.Type.AGREE)
        assert opinion.pk is not None
        assert opinion.opinion_type == "agree"

    def test_str(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        opinion = Opinion.objects.create(created_by=user, discussion=discussion, opinion_type=Opinion.Type.DISAGREE)
        assert "disagree" in str(opinion)

    def test_unique_participant_node(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        Opinion.objects.create(created_by=user, discussion=discussion, opinion_type=Opinion.Type.AGREE)
        with pytest.raises(IntegrityError):
            Opinion.objects.create(created_by=user, discussion=discussion, opinion_type=Opinion.Type.DISAGREE)
