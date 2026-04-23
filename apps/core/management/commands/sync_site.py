from __future__ import annotations

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Synchronize the Django Site record with configured settings."

    def handle(self, *args: object, **options: object) -> None:
        Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={
                "domain": settings.SITE_DOMAIN,
                "name": settings.SITE_NAME,
            },
        )
