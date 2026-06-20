from django.apps import AppConfig


class AcademicsConfig(AppConfig):
    """Academic structure — the skeleton the rest of the system hangs off."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.academics"
    label = "academics"
    verbose_name = "Academics"
