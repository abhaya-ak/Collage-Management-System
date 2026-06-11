from django.apps import AppConfig


class CoreConfig(AppConfig):
    """System foundation app. Holds reusable base classes only — no business logic."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"
