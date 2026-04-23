from __future__ import annotations

import pytest
from django.contrib.sites.models import Site
from django.core.management import call_command


@pytest.mark.django_db
def test_sync_site_updates_the_configured_site(settings) -> None:
    settings.SITE_ID = 1
    settings.SITE_NAME = "Collective"
    settings.SITE_DOMAIN = "collective.example.com"
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={"domain": "example.com", "name": "example.com"},
    )

    call_command("sync_site", verbosity=0)

    site = Site.objects.get(id=settings.SITE_ID)
    assert site.name == "Collective"
    assert site.domain == "collective.example.com"
