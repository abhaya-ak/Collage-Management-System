from django.contrib import admin

from auth_core.admin_base import RBACAdmin, ReadOnlyRBACAdmin
from auth_core.services.rbac_service import RBACService
from academics.models import Result, Routine, ExamRoutine, Faculty


# ─────────────────────────────────────────────────────────────────────────────
# ResultAdmin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Result)
class ResultAdmin(RBACAdmin):
    """
    Grades management with fine-grained RBAC.

    Because the project uses 'academics.manage_result' (not 'add' / 'change'),
    we override the add / change permission codes explicitly.

    PERMISSION MAPPING
    ──────────────────
    View   → academics.view_result    (PermissionCodes.ACADEMICS_VIEW_RESULT)
    Add    → academics.manage_result  (PermissionCodes.ACADEMICS_MANAGE_RESULT)
    Change → academics.manage_result
    Delete → academics.delete_result  (auto-generated; restrict to superuser if
                                       destructive deletes should be forbidden)

    Tenant filter: students can only view their own results (row-level isolation).
    """

    # ── Custom permission codes ───────────────────────────────────────────────
    view_permission   = "academics.view_result"
    add_permission    = "academics.manage_result"   # 'manage' verb from PermissionCodes
    change_permission = "academics.manage_result"
    delete_permission = "academics.delete_result"   # auto-generated fallback is fine

    # ── Display ───────────────────────────────────────────────────────────────
    list_display   = ["student", "exam_routine", "marks_obtained", "grade", "is_published", "is_absent"]
    list_filter    = ["grade", "is_published", "is_absent", "exam_routine__exam_type"]
    search_fields  = ["student__username", "student__first_name", "exam_routine__subject__code"]
    ordering       = ["-exam_routine__exam_date"]
    readonly_fields = ["created_at", "updated_at"]
    actions        = ["publish_results", "unpublish_results"]

    # ── Bulk actions ──────────────────────────────────────────────────────────
    @admin.action(description="📢 Publish selected results")
    def publish_results(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "Permission denied.", level="error")
            return
        updated = queryset.update(is_published=True)
        self.message_user(request, f"{updated} result(s) published.")

    @admin.action(description="🔒 Unpublish selected results")
    def unpublish_results(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "Permission denied.", level="error")
            return
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated} result(s) unpublished.")

    # ── Tenant-aware queryset ─────────────────────────────────────────────────
    def get_tenant_filter(self, request):
        """
        Students can only see their own results in the admin dashboard.

        In practice students should not have is_staff=True; this is a defence
        in depth guard for edge cases where a student account is accidentally
        elevated.
        """
        role = RBACService.get_role(request.user)
        if role == "student":
            return {"student": request.user}
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# RoutineAdmin (Class Timetable)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Routine)
class RoutineAdmin(RBACAdmin):
    """
    Class routine / timetable management.

    Permission codes (auto-generated):
      academics.view_routine     → PermissionCodes.ACADEMICS_VIEW_TIMETABLE (alias below)
      academics.manage_routine   → PermissionCodes.ACADEMICS_MANAGE_TIMETABLE
    """

    view_permission   = "academics.view_timetable"
    add_permission    = "academics.manage_timetable"
    change_permission = "academics.manage_timetable"
    delete_permission = "academics.manage_timetable"

    list_display  = ["subject", "section", "day_of_week", "start_time", "end_time", "room", "is_active"]
    list_filter   = ["day_of_week", "is_active", "subject__name"]
    search_fields = ["subject__code", "subject__name", "room", "section"]
    ordering      = ["day_of_week", "start_time"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ExamRoutine)
class ExamRoutineAdmin(RBACAdmin):
    """
    Exam schedule management.  Shares the same permission codes as Routine.
    """

    view_permission   = "academics.view_timetable"
    add_permission    = "academics.manage_timetable"
    change_permission = "academics.manage_timetable"
    delete_permission = "academics.manage_timetable"

    list_display  = ["subject", "exam_type", "exam_date", "start_time", "room", "full_marks", "pass_marks"]
    list_filter   = ["exam_type", "exam_date"]
    search_fields = ["subject__code", "subject__name", "room"]
    ordering      = ["exam_date", "start_time"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Faculty)
class FacultyAdmin(RBACAdmin):
    """
    Faculty / department management.

    Auto-generated codes:
      academics.view_faculty
      academics.add_faculty
      academics.change_faculty
      academics.delete_faculty
    """

    list_display  = ["name", "description", "created_at"]
    search_fields = ["name"]
    ordering      = ["name"]
    readonly_fields = ["created_at", "updated_at"]
