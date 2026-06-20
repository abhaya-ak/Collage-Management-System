from django.apps import AppConfig


class FacultyConfig(AppConfig):
    """Faculty domain — teacher identity and teaching assignments."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.faculty"
    label = "faculty"
    verbose_name = "Faculty"
