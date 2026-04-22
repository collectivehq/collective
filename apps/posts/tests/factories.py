from __future__ import annotations

import factory

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services
from apps.posts.models import Post, PostRevision
from apps.spaces.tests.factories import SpaceFactory
from apps.users.tests.factories import UserFactory


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    space = factory.SubFactory(SpaceFactory)
    discussion = factory.SubFactory(DiscussionFactory, space=factory.SelfAttribute("..space"))
    author = factory.SubFactory(UserFactory)
    content = factory.Faker("paragraph")
    is_draft = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        discussion = kwargs.pop("discussion")
        author = kwargs.pop("author")
        content = kwargs.pop("content")
        is_draft = kwargs.pop("is_draft", False)
        if discussion.space.is_active:
            return post_services.create_post(
                discussion=discussion,
                author=author,
                content=content,
                is_draft=is_draft,
            )

        post = Post.objects.create(
            discussion=discussion,
            created_by=author,
            is_draft=is_draft,
            sequence_index=kwargs.pop("sequence_index", 0),
        )
        PostRevision.objects.create(post=post, content=content, created_by=author)
        return post
