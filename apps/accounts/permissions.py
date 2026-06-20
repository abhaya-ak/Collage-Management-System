"""
Sprint 4 — Step 5: Permission engine (RBAC enforcement for DRF views).

The resolution logic lives on the user model (user.has_role / user.has_permission).
These classes/factories make it reusable in views:

    class StudentCreateView(...):
        permission_classes = [IsAuthenticated, HasPermission("create_student")]

    class AdminOnlyView(...):
        permission_classes = [IsAuthenticated, HasRole("ADMIN")]
"""

from rest_framework.permissions import BasePermission


class HasPermission(BasePermission):
    """Allow access only if the user has a specific permission code."""

    message = "You do not have the required permission."

    def __init__(self, permission_code: str | None = None):
        self.permission_code = permission_code

    # Lets you write `HasPermission("create_student")` in permission_classes.
    def __call__(self):
        return self

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Allow a view-level attribute as a fallback.
        code = self.permission_code or getattr(view, "required_permission", None)
        if code is None:
            return True
        return user.has_permission(code)


class HasRole(BasePermission):
    """Allow access only if the user has one of the given roles."""

    message = "You do not have the required role."

    def __init__(self, *role_names: str):
        self.role_names = role_names

    def __call__(self):
        return self

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        roles = self.role_names or tuple(getattr(view, "required_roles", ()))
        if not roles:
            return True
        return any(user.has_role(r) for r in roles)
