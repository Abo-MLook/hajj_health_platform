from django.apps import AppConfig


class PilgrimsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pilgrims"

    def ready(self):
        import apps.pilgrims.signals  # noqa: F401
