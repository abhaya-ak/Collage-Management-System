# auth_core/services/rbac_service.py
from users.models import UserRole, RolePermission


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

        setattr(user, cache_attr, perms)
        return perms

    @staticmethod
    def has_permission(user, code: str) -> bool:
        """Single permission check. Superusers bypass all RBAC."""
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        return code in RBACService.load_permissions(user)

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
