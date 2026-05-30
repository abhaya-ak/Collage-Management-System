# auth_core/checks.py
#
# Django system checks for RBAC deployment safety.
# Registered via AuthCoreConfig.ready() in apps.py.
#
# These checks run when:
#   - python manage.py check
#   - python manage.py runserver (on startup)
#   - python manage.py migrate (post-migration)
#
# They do NOT block startup (Warning, not Error) so that the app
# can still run in test/CI environments before the DB is ready.

import logging

from django.core.checks import Warning, register

logger = logging.getLogger('auth_core.rbac')

W001 = 'auth_core.W001'
W002 = 'auth_core.W002'


@register()
def check_rbac_seeded(app_configs, **kwargs):
    """
    Warns if the Permission table is empty.

    An empty Permission table means seed_roles was never run.
    Runtime effect: every HasPermission check returns False → 403 on all
    protected endpoints for every authenticated user.

    Safe to fail silently if the table doesn't exist yet (pre-migration).
    """
    errors = []
    try:
        from users.models import Permission  # noqa: PLC0415
        if not Permission.objects.exists():
            msg = (
                'The RBAC Permission table is empty — seed_roles has not been run. '
                'Every authenticated user will receive 403 on all protected endpoints. '
                'Fix: python manage.py seed_roles'
            )
            logger.warning('SYSTEM CHECK: %s', msg)
            errors.append(
                Warning(
                    msg,
                    hint='Run this once after deployment and after any change to ROLE_PERMISSION_MAP.',
                    obj=None,
                    id=W001,
                )
            )
    except Exception:
        # Table doesn't exist yet (pre-migration) or DB unreachable — skip silently.
        pass
    return errors


@register()
def check_users_without_roles(app_configs, **kwargs):
    """
    Warns if any User row has no corresponding UserRole row.

    Users without a role get 403 on every protected endpoint. This is the
    most common silent failure: admin creates a user via Django admin panel
    (which does not auto-assign a role) without using POST /api/v1/users/.

    Only runs if both tables exist and are accessible.
    """
    errors = []
    try:
        from django.contrib.auth import get_user_model  # noqa: PLC0415
        from users.models import UserRole               # noqa: PLC0415

        User = get_user_model()
        users_without_roles = (
            User.objects
            .exclude(pk__in=UserRole.objects.values_list('user_id', flat=True))
            .filter(is_active=True, is_superuser=False)
            .values_list('pk', 'username')
        )
        count = users_without_roles.count()
        if count:
            pks = list(users_without_roles[:5])  # show first 5 max
            msg = (
                f'{count} active non-superuser account(s) have no role assigned '
                f'and will receive 403 on all protected endpoints. '
                f'First affected (pk, username): {pks}. '
                f'Fix: PATCH /api/v1/users/<pk>/role/ or Django admin.'
            )
            logger.warning('SYSTEM CHECK: %s', msg)
            errors.append(
                Warning(
                    msg,
                    hint='Assign roles via PATCH /api/v1/users/{pk}/role/ for each affected user.',
                    obj=None,
                    id=W002,
                )
            )
    except Exception:
        pass
    return errors
