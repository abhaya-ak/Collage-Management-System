from django.apps import AppConfig


class FeesConfig(AppConfig):
    """Fees & finance domain. Build order: FeeStructure -> FeeComponent ->
    StudentFee -> Payment -> Receipt."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.fees"
    label = "fees"
    verbose_name = "Fees"
