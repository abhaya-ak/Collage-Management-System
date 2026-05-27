"""
auth_core/admin_base.py
=======================
Production-grade Django admin base class that integrates with the project's
custom RBACService instead of Django's built-in permission framework.

WHY THIS FILE EXISTS
─────────────────────
Django admin and DRF APIs use COMPLETELY DIFFERENT permission mechanisms:

  DRF  → checks request.user via permission_classes on every API view.
         Your HasPermission class already wires this to RBACService.

  Admin → calls ModelAdmin.has_*_permission() which, by default, delegates
          to django.contrib.auth's Permission table (ContentType-based).
          Since your project never populates that table (you use a custom
          users.Permission model), Django admin falls back to is_staff / is_superuser
          only — every model appears or disappears based on is_staff, not on RBAC.

SOLUTION
─────────
Override all five has_*_permission hooks on a shared RBACAdmin base class
to call RBACService.has_permission() instead.  Every domain ModelAdmin that
inherits RBACAdmin gets RBAC enforcement for free.

PERMISSION CODE FORMAT (mirrors PermissionCodes in users/constants.py)
─────────────────────────────────────────────────────────────────────────
  <app_label>.<action>_<model_lower>

  Examples:
    academics.view_result
    academics.change_result
    students.view_student
    students.add_student
    students.delete_student

The class derives these codes automatically from model metadata so you rarely
need to override them.  When needed, set class attributes to customise:

  class ResultAdmin(RBACAdmin):
      view_permission   = 'academics.view_result'
      add_permission    = 'academics.add_result'        # defaults to manage_result
      change_permission = 'academics.change_result'
      delete_permission = 'academics.delete_result'
"""

import logging

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from auth_core.services.rbac_service import RBACService

logger = logging.getLogger("auth_core.admin_rbac")

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_perm(app_label: str, action: str, model_name: str) -> str:
    """Construct a canonical RBAC permission code."""
    return f"{app_label}.{action}_{model_name.lower()}"


def _superuser_or(user, fallback: bool) -> bool:
    """Superusers bypass all RBAC. Otherwise return fallback value."""
    if getattr(user, "is_superuser", False):
        return True
    return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Audit helpers
# ─────────────────────────────────────────────────────────────────────────────

def _audit_admin_action(request: HttpRequest, action: str, model_name: str, obj=None) -> None:

    try:
        user = getattr(request, "user", None)
        obj_repr = repr(obj) if obj else "—"
        logger.debug(
            "ADMIN_ACTION | user=%s | action=%s | model=%s | object=%s",
            getattr(user, "username", "anonymous"),
            action,
            model_name,
            obj_repr,
        )
    except Exception:
        # Audit failure must never crash the admin.
        pass


# ─────────────────────────────────────────────────────────────────────────────
# RBACAdmin — the single base class all domain admins should inherit from
# ─────────────────────────────────────────────────────────────────────────────

class RBACAdmin(admin.ModelAdmin):
    """
    Drop-in replacement for admin.ModelAdmin that gates every admin action
    through RBACService instead of Django's built-in permission framework.

    USAGE
    ─────
    1. Inherit instead of admin.ModelAdmin:

        @admin.register(Student)
        class StudentAdmin(RBACAdmin):
            list_display = [...]

    2. Optionally override permission codes if the auto-generated ones differ
       from your PermissionCodes constants:

        @admin.register(Result)
        class ResultAdmin(RBACAdmin):
            view_permission   = 'academics.view_result'
            change_permission = 'academics.manage_result'   # custom verb
            # add / delete will still be auto-generated as academics.add_result etc.

    AUTOMATIC CODE GENERATION
    ──────────────────────────
    From a model registered under the 'academics' app with class name 'Result':
        view   → academics.view_result
        add    → academics.add_result
        change → academics.change_result
        delete → academics.delete_result

    READONLY ROLE SUPPORT
    ─────────────────────
    Set readonly_role = True on any subclass to block add/change/delete
    regardless of RBAC — useful for inspector or auditor roles that should
    only read via the admin dashboard.

    TENANT-AWARE QUERYSET FILTERING
    ────────────────────────────────
    Override get_tenant_filter(request) to return a dict of Q-compatible
    kwargs that will be applied to every queryset. This keeps row-level
    isolation trivial without duplicating filter logic across list_display,
    search, etc.

        def get_tenant_filter(self, request):
            role = RBACService.get_role(request.user)
            if role == 'teacher':
                return {'department': request.user.teacher.department}
            return {}
    """

    # ── Permission code overrides (set on subclass when needed) ──────────────
    view_permission:   str | None = None
    add_permission:    str | None = None
    change_permission: str | None = None
    delete_permission: str | None = None

    # ── Readonly-role flag ────────────────────────────────────────────────────
    # True → add / change / delete are always denied even if RBAC would allow
    readonly_role: bool = False

    # ── Audit write actions? (set False to disable for high-volume models) ───
    enable_audit: bool = True

    # ─────────────────────────────────────────────────────────────────────────
    # Internal: permission code resolution
    # ─────────────────────────────────────────────────────────────────────────

    def _get_app_label(self) -> str:
        return self.model._meta.app_label

    def _get_model_name(self) -> str:
        return self.model._meta.model_name  # already lower-cased by Django

    def _perm(self, action: str, override: str | None) -> str:
        """Return the override if provided, else auto-generate."""
        if override:
            return override
        return _build_perm(self._get_app_label(), action, self._get_model_name())

    # ─────────────────────────────────────────────────────────────────────────
    # Five Django admin permission hooks — all delegate to RBACService
    # ─────────────────────────────────────────────────────────────────────────

    def has_module_permission(self, request: HttpRequest) -> bool:
        """
        Controls whether the app's section appears in the admin index.

        Django calls this to decide whether to show the app block in the
        sidebar.  We grant it if the user has AT LEAST view permission on
        this model — matching the intuition "can I see it? → show the app".
        """
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True

        view_code = self._perm("view", self.view_permission)
        return RBACService.has_permission(user, view_code)

    def has_view_permission(self, request: HttpRequest, obj=None) -> bool:
        """
        Grants access to the changelist and detail read views.

        Also called by Django to decide if a model link appears at all in
        the app index section — so this is the primary visibility gate.
        """
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True

        view_code = self._perm("view", self.view_permission)
        allowed = RBACService.has_permission(user, view_code)

        if allowed and self.enable_audit:
            _audit_admin_action(request, "view", self._get_model_name(), obj)

        return allowed

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Grants the 'Add' button and POST to the creation form.

        Blocked unconditionally when readonly_role = True.
        """
        if self.readonly_role:
            return False
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True

        add_code = self._perm("add", self.add_permission)
        return RBACService.has_permission(user, add_code)

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """
        Grants the 'Save' button and inline edit access.

        Blocked unconditionally when readonly_role = True.
        """
        if self.readonly_role:
            return False
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True

        change_code = self._perm("change", self.change_permission)
        allowed = RBACService.has_permission(user, change_code)

        if allowed and obj and self.enable_audit:
            _audit_admin_action(request, "change", self._get_model_name(), obj)

        return allowed

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        """
        Grants the 'Delete' button and the bulk-delete action.

        Blocked unconditionally when readonly_role = True.
        """
        if self.readonly_role:
            return False
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True

        delete_code = self._perm("delete", self.delete_permission)
        allowed = RBACService.has_permission(user, delete_code)

        if allowed and obj and self.enable_audit:
            _audit_admin_action(request, "delete", self._get_model_name(), obj)

        return allowed

    # ─────────────────────────────────────────────────────────────────────────
    # Tenant-aware secure queryset filtering
    # ─────────────────────────────────────────────────────────────────────────

    def get_tenant_filter(self, request: HttpRequest) -> dict:
        """
        Override in subclasses to return row-level filter kwargs.

        Example (TeacherAdmin — teachers only see their own department's data):
            def get_tenant_filter(self, request):
                role = RBACService.get_role(request.user)
                if role == 'teacher':
                    return {'teacher__user': request.user}
                return {}

        Returning an empty dict (default) means no additional filtering —
        all rows visible to users who have the view permission.
        """
        return {}

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Applies tenant filter on top of the base queryset.

        This is the secure default.  Superusers are NOT filtered so they
        retain full visibility for debugging and support.
        """
        qs = super().get_queryset(request)

        if getattr(request.user, "is_superuser", False):
            return qs

        tenant_filter = self.get_tenant_filter(request)
        if tenant_filter:
            qs = qs.filter(**tenant_filter)

        return qs


# ─────────────────────────────────────────────────────────────────────────────
# ReadOnlyRBACAdmin — convenience subclass for inspector / read-only roles
# ─────────────────────────────────────────────────────────────────────────────

class ReadOnlyRBACAdmin(RBACAdmin):
    """
    RBAC-aware admin that only ever grants read access.

    Useful for roles like 'finance' or 'receptionist' that need to browse
    data in the admin dashboard but must never mutate it.

    All write actions are disabled at the class level; the 'Add' button and
    'Save' / 'Delete' controls are hidden automatically.
    """

    readonly_role = True

    def get_readonly_fields(self, request, obj=None):
        """Mark every model field as readonly so the form renders but is inert."""
        return [field.name for field in self.model._meta.get_fields()
                if hasattr(field, 'name')]


# ─────────────────────────────────────────────────────────────────────────────
# Permission auto-generation helper (called from management commands / seeds)
# ─────────────────────────────────────────────────────────────────────────────

def generate_model_permissions(model_class) -> list[dict]:
    """
    Generate the canonical set of CRUD permission dicts for a model.

    Returns a list of dicts suitable for bulk_create into users.Permission:

        [
          {'code': 'students.view_student',   'name': 'View Student',   'module': 'students'},
          {'code': 'students.add_student',    'name': 'Add Student',    'module': 'students'},
          {'code': 'students.change_student', 'name': 'Change Student', 'module': 'students'},
          {'code': 'students.delete_student', 'name': 'Delete Student', 'module': 'students'},
        ]

    Usage in a management command or seed script:
        from auth_core.admin_base import generate_model_permissions
        from students.models import Student

        for perm_dict in generate_model_permissions(Student):
            Permission.objects.get_or_create(code=perm_dict['code'], defaults=perm_dict)
    """
    app_label  = model_class._meta.app_label
    model_name = model_class._meta.model_name  # lower-cased
    verbose    = model_class._meta.verbose_name.title()

    actions = ["view", "add", "change", "delete"]
    return [
        {
            "code":   f"{app_label}.{action}_{model_name}",
            "name":   f"{action.capitalize()} {verbose}",
            "module": app_label,
        }
        for action in actions
    ]
