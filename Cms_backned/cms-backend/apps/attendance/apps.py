from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    """Attendance domain — sessions and per-student records."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.attendance"
    label = "attendance"
    verbose_name = "Attendance"
