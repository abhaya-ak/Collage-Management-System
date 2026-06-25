"""
Phase 3 — Accounts: Identity, Authentication, Authorization (RBAC).

Build order:
    1. CustomUser      -> identity (email login)
    2. Role            -> real role model (NOT an enum on the user)
    3. UserRole        -> User <-> Role bridge (a user can hold multiple roles)
    4. Permission      -> granular permissions (create_student, collect_fee, ...)
    5. RolePermission  -> Role <-> Permission bridge (flexible RBAC)
"""

from django.contrib.auth.models import AbstractBaseUser
from django.db import models

from apps.accounts.managers import CustomUserManager
from apps.core.enums import UserRole as RoleChoices  # enum (aliased to avoid clash)
from apps.core.models import BaseModel, SoftDeleteMixin
from apps.core.validators import validate_image, validate_phone_number


# =============================================================
# Step 1 — CustomUser
# =============================================================
class CustomUser(AbstractBaseUser, BaseModel, SoftDeleteMixin):
    """
    The identity everything else references (students, faculty, audit logs...).
    Authenticates by EMAIL. We use a custom RBAC (Role/Permission below) instead
    of Django's PermissionsMixin.
    """

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(
        max_length=20, blank=True, validators=[validate_phone_number]
    )
    profile_photo = models.ImageField(
        upload_to="users/photos/", blank=True, null=True, validators=[validate_image]
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # can access Django admin
    is_superuser = models.BooleanField(default=False)  # full access bypass
    must_change_password = models.BooleanField(default=False)  # force change on first login

    roles = models.ManyToManyField(
        "Role", through="UserRole", related_name="users", blank=True
    )

    objects = CustomUserManager()
    all_objects = models.Manager()  # includes soft-deleted users

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]
        default_manager_name = "objects"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def delete(self, using=None, keep_parents=False, hard=False):
        """Soft delete also disables the account so it can't authenticate."""
        if not hard:
            self.is_active = False
        return super().delete(using=using, keep_parents=keep_parents, hard=hard)

    # --- Minimal hooks so Django admin works for superusers ---
    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser

    # --- RBAC engine ---------------------------------------------------------
    # Flow:  User -> UserRole -> Role -> RolePermission -> Permission
    def get_role_names(self) -> set[str]:
        """Active role names assigned to this user."""
        return set(
            self.user_roles.filter(
                is_deleted=False, role__is_deleted=False
            ).values_list("role__name", flat=True)
        )

    def get_permission_codes(self) -> set[str]:
        """All active permission codes granted through this user's roles."""
        return set(
            Permission.objects.filter(
                is_deleted=False,
                permission_roles__is_deleted=False,
                permission_roles__role__is_deleted=False,
                permission_roles__role__role_users__is_deleted=False,
                permission_roles__role__role_users__user=self,
            )
            .values_list("code", flat=True)
            .distinct()
        )

    def has_role(self, role_name: str) -> bool:
        """True if the user holds the given role (superuser always True)."""
        if self.is_superuser:
            return True
        return role_name in self.get_role_names()

    def has_permission(self, permission_code: str) -> bool:
        """True if any of the user's roles grants the permission (superuser always True)."""
        if self.is_superuser:
            return True
        return permission_code in self.get_permission_codes()


# =============================================================
# Step 2 — Role
# =============================================================
class Role(BaseModel, SoftDeleteMixin):
    """A real role model (future-proof; supports multi-role users)."""

    name = models.CharField(max_length=50, unique=True, choices=RoleChoices.choices)
    description = models.CharField(max_length=255, blank=True)

    permissions = models.ManyToManyField(
        "Permission", through="RolePermission", related_name="roles", blank=True
    )

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.get_name_display()


# =============================================================
# Step 3 — UserRole (User <-> Role bridge)
# =============================================================
class UserRole(BaseModel, SoftDeleteMixin):
    """Bridge: a user can hold multiple roles (e.g. Teacher + Accountant)."""

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(
        "Role", on_delete=models.CASCADE, related_name="role_users"
    )

    class Meta:
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"], name="unique_user_role"
            )
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.role.name}"


# =============================================================
# Step 4 — Permission
# =============================================================
class Permission(BaseModel, SoftDeleteMixin):
    """Granular action permission, e.g. code='create_student'."""

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ["code"]

    def __str__(self):
        return self.code


# =============================================================
# Step 5 — RolePermission (Role <-> Permission bridge)
# =============================================================
class RolePermission(BaseModel, SoftDeleteMixin):
    """Bridge: assign permissions to roles. Makes RBAC flexible."""

    role = models.ForeignKey(
        "Role", on_delete=models.CASCADE, related_name="role_permissions"
    )
    permission = models.ForeignKey(
        "Permission", on_delete=models.CASCADE, related_name="permission_roles"
    )

    class Meta:
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="unique_role_permission"
            )
        ]

    def __str__(self):
        return f"{self.role.name} -> {self.permission.code}"