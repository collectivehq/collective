from __future__ import annotations

from django.apps import AppConfig


class ReactionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reactions"
    verbose_name = "Reactions"

    def ready(self) -> None:
        import apps.reactions.signals  # noqa: F401
