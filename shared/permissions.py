"""
Action-based RBAC permission for DRF viewsets.

A viewset declares a `permission_map` of {action: permission_code}. This class
checks the current user against the code for the current action.

    class ProgramViewSet(BaseRBACViewSet):
        permission_map = {
            "list": "view_program",
            "create": "create_program",
            ...
        }
"""

from rest_framework.permissions import BasePermission


class ActionPermission(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        permission_map = getattr(view, "permission_map", {}) or {}
        code = permission_map.get(view.action)
        if code is None:
            # Action not explicitly restricted -> allow (still authenticated).
            return True
        return user.has_permission(code)
