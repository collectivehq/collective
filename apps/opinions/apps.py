from django.apps import AppConfig


class OpinionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.opinions"
    verbose_name = "Opinions"

    def ready(self) -> None:
        import apps.opinions.signals  # noqa: F401
