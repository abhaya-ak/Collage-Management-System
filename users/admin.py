from django.contrib import admin
from django.contrib.auth import get_user_model

from auth_core.admin_base import RBACAdmin
from users.models import Role, Permission, RolePermission, UserRole

User = get_user_model()

@admin.register(Role)
class RoleAdmin(RBACAdmin):
    add_permission    = "users.manage_users"
    change_permission = "users.manage_users"
    delete_permission = "users.manage_users"

    list_display  = ["name"]
    search_fields = ["name"]
    ordering      = ["name"]

@admin.register(Permission)
class PermissionAdmin(RBACAdmin):
    add_permission    = "users.manage_users"
    change_permission = "users.manage_users"
    delete_permission = "users.manage_users"

    list_display  = ["code", "name", "module"]
    list_filter   = ["module"]
    search_fields = ["code", "name", "module"]
    ordering      = ["module", "code"]

@admin.register(RolePermission)
class RolePermissionAdmin(RBACAdmin):
    add_permission    = "users.manage_users"
    change_permission = "users.manage_users"
    delete_permission = "users.manage_users"

    list_display  = ["role", "permission"]
    list_filter   = ["role"]
    search_fields = ["role__name", "permission__code", "permission__module"]
    ordering      = ["role__name", "permission__module"]

@admin.register(UserRole)
class UserRoleAdmin(RBACAdmin):
    add_permission    = "users.manage_users"
    change_permission = "users.manage_users"
    delete_permission = "users.manage_users"

    list_display  = ["user", "role"]
    list_filter   = ["role"]
    search_fields = ["user__username", "user__email", "role__name"]
    ordering      = ["role__name", "user__username"]
    raw_id_fields = ["user"]
