# auth_core/services/rbac_service.py
import logging

from users.models import UserRole, RolePermission

logger = logging.getLogger('auth_core.rbac')


class RBACService:
    """
    Loads and evaluates role-based permissions from the existing
    users.Role / users.Permission / users.RolePermission models.

    Permission codes are cached on the user object for the lifetime
    of the request so the DB is only hit once per request.
    """

    @staticmethod
    def load_permissions(user) -> set:
        """
        Returns the set of permission codes for this user.
        e.g. {'academics.view_result', 'fees.verify_payment'}

        Also adds a synthetic 'role:<name>' entry so views can do:
            required_permission = 'role:admin'

        Silent failure modes — both are now logged as WARNING:
          1. UserRole.DoesNotExist  → user has no role assigned (missing UserRole row)
          2. RolePermission empty   → DB not seeded (seed_roles not run)
        """
        if not user or not getattr(user, 'is_authenticated', False):
            return set()

        cache_attr = f'_rbac_perms_{user.pk}'
        cached = getattr(user, cache_attr, None)
        if cached is not None:
            return cached

        try:
            user_role = UserRole.objects.select_related('role').get(user=user)
        except UserRole.DoesNotExist:
            # RISK 2 — user has no role assigned. Common causes:
            #   - Admin created the user via Django admin without assigning a role
            #   - AuthService.register() crashed between User.create() and UserRole.create()
            #   - User was created directly in DB/shell without a role
            # Effect: every HasPermission check returns False → 403 on all endpoints.
            logger.warning(
                'RBAC: user pk=%s has no UserRole row — all permission checks will fail. '
                'Assign a role via PATCH /api/v1/users/%s/role/ or Django admin.',
                user.pk, user.pk,
            )
            perms = set()
            setattr(user, cache_attr, perms)
            return perms

        perms = set(
            RolePermission.objects
            .filter(role=user_role.role)
            .values_list('permission__code', flat=True)
        )
        # Synthetic role-level permission for broad role checks
        perms.add(f'role:{user_role.role.name}')

        # RISK 1 — if only the synthetic key is present, RolePermission table is empty.
        # This almost always means seed_roles was never run.
        # Effect: every individual HasPermission check returns False → 403 on all endpoints.
        if len(perms) == 1:
            logger.warning(
                'RBAC: user pk=%s role=%s has no Permission rows (only synthetic role key). '
                'The RolePermission table is likely empty. '
                'Run: python manage.py seed_roles',
                user.pk, user_role.role.name,
            )

        setattr(user, cache_attr, perms)
        return perms


    @staticmethod
    def has_permission(user, code: str) -> bool:
        """
        Single permission check.

        Bypass order (highest to lowest):
          1. user.is_superuser=True        — Django-level god mode
          2. role:super_admin              — RBAC-level god mode (no is_superuser flag required)
          3. code in user's permission set — standard RBAC check

        Using role:super_admin bypass means no individual permission codes need to be
        added to ROLE_PERMISSION_MAP for super_admin — it automatically supersedes admin.
        """
        from users.constants import RoleNames
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        perms = RBACService.load_permissions(user)
        # super_admin bypasses individual code checks — equivalent to is_superuser at RBAC layer
        if f'role:{RoleNames.SUPER_ADMIN}' in perms:
            return True
        return code in perms

    @staticmethod
    def get_role(user) -> str | None:
        """Returns the role name string or None if no role is assigned."""
        try:
            return (
                UserRole.objects
                .select_related('role')
                .get(user=user)
                .role.name
            )
        except UserRole.DoesNotExist:
            return None
