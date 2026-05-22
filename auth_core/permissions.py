# auth_core/permissions.py
from rest_framework.permissions import BasePermission

from auth_core.services.rbac_service import RBACService


class HasPermission(BasePermission):
    """
    Drop-in replacement for IsAuthenticated + IsAdminUser.

    Usage in any ViewSet:

        from auth_core.permissions import HasPermission

        class MyViewSet(viewsets.ModelViewSet):
            permission_classes    = [HasPermission]
            required_permission   = 'academics.view_result'

    If `required_permission` is not set on the view, behaves like
    IsAuthenticated (user must be logged in, no specific perm needed).

    Superusers always pass all checks.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser bypasses all RBAC
        if getattr(request.user, 'is_superuser', False):
            return True

        code = getattr(view, 'required_permission', None)
        if not code:
            # No specific permission required — just needs to be authenticated
            return True

        return RBACService.has_permission(request.user, code)


class IsAdminRole(BasePermission):
    """
    Replaces IsAdminUser — checks RBAC 'role:admin' instead of is_staff flag.
    Use this for actions that only admin-role users should perform.

    Superusers always pass.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False):
            return True
        return 'role:admin' in RBACService.load_permissions(request.user)
