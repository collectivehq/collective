from __future__ import annotations

import pytest

from apps.discussions.tests.factories import DiscussionFactory
from apps.opinions import services as opinion_services
from apps.opinions.models import Opinion
from apps.spaces import services as space_services
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestCastOpinion:
    def test_toggle_opinion(self, space_with_participant):
        space, participant, discussion = space_with_participant
        opinion = opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="agree")
        assert opinion.opinion_type == "agree"

    def test_update_opinion(self, space_with_participant):
        space, participant, discussion = space_with_participant
        opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="agree")
        opinion = opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="disagree")
        assert opinion.opinion_type == "disagree"
        assert Opinion.objects.filter(created_by=participant.user, discussion=discussion).count() == 1

    def test_invalid_type_raises(self, space_with_participant):
        space, participant, discussion = space_with_participant
        with pytest.raises(ValueError, match="not enabled"):
            opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="abstain")


@pytest.mark.django_db
class TestGetOpinionCounts:
    def test_counts(self, space_with_participant):
        space, participant, discussion = space_with_participant
        opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="agree")

        joiner2 = UserFactory()
        p2 = space_services.join_space(space=space, user=joiner2)
        opinion_services.toggle_opinion(user=p2.user, discussion=discussion, opinion_type="disagree")

        counts = opinion_services.get_opinion_counts(discussion)
        assert counts["agree"] == 1
        assert counts["disagree"] == 1


@pytest.mark.django_db
class TestGetOpinionCountsBatch:
    def test_batch_counts(self, space_with_participant):
        space, participant, discussion = space_with_participant
        second_discussion = DiscussionFactory(space=space)
        opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="agree")
        opinion_services.toggle_opinion(user=participant.user, discussion=second_discussion, opinion_type="disagree")
        counts = opinion_services.get_opinion_counts_batch([discussion.pk, second_discussion.pk])
        assert counts[discussion.pk]["agree"] == 1
        assert counts[second_discussion.pk]["disagree"] == 1

    def test_batch_empty_list(self, space_with_participant):
        counts = opinion_services.get_opinion_counts_batch([])
        assert counts == {}


@pytest.mark.django_db
class TestToggleOpinionRemoval:
    def test_toggle_same_opinion_removes(self, space_with_participant):
        space, participant, discussion = space_with_participant
        opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="agree")
        result = opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="agree")
        assert result is None
        assert not Opinion.objects.filter(created_by=participant.user, discussion=discussion).exists()


@pytest.mark.django_db
class TestGetUserOpinion:
    def test_returns_type_when_exists(self, space_with_participant):
        space, participant, discussion = space_with_participant
        opinion_services.toggle_opinion(user=participant.user, discussion=discussion, opinion_type="agree")
        result = opinion_services.get_user_opinion_type(user=participant.user, discussion=discussion)
        assert result == "agree"

    def test_returns_none_when_no_opinion(self, space_with_participant):
        space, participant, discussion = space_with_participant
        result = opinion_services.get_user_opinion_type(user=participant.user, discussion=discussion)
        assert result is None
