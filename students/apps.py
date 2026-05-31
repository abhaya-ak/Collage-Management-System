from django.apps import AppConfig


class StudentsConfig(AppConfig):
    name = 'students'

    def ready(self):
        import students.signals  # noqa: F401 — registers post_save signal on UserRole
