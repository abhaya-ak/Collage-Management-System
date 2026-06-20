from django.apps import AppConfig


class ExamsConfig(AppConfig):
    """Exam & Result domain. Grading engine is the foundation."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.exams"
    label = "exams"
    verbose_name = "Exams"
