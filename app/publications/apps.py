from django.apps import AppConfig


class PublicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.publications"
    verbose_name = "Publications"

    def ready(self):
        from . import signals  # noqa: F401
