from django.apps import AppConfig


class StudentsConfig(AppConfig):
    """Students domain — the source of truth for student identity & enrollment."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.students"
    label = "students"
    verbose_name = "Students"
