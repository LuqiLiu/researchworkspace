from django.apps import AppConfig


class ResearchObjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.research_objects"
    verbose_name = "Research objects"

    def ready(self):
        from . import signals  # noqa: F401
