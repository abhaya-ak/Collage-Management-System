from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Identity, authentication, and authorization (RBAC)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"