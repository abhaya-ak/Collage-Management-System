from django.apps import AppConfig


class AuthCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auth_core'
    verbose_name = 'Auth Core'

    def ready(self):
        # Register RBAC deployment safety checks.
        # These surface in `python manage.py check` and on runserver startup.
        from . import checks  # noqa: F401
