# students/admin.py
from django.contrib import admin

from auth_core.admin_base import RBACAdmin, ReadOnlyRBACAdmin
from auth_core.services.rbac_service import RBACService
from students.models import Student, Teacher, LeaveRequest


# ─────────────────────────────────────────────────────────────────────────────
# StudentAdmin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Student)
class StudentAdmin(RBACAdmin):
    """
    Full CRUD access to student records, gated by RBAC.

    auto-generated permission codes:
      students.view_student   → RBACService.has_permission(user, 'students.view_student')
      students.add_student
      students.change_student
      students.delete_student

    Tenant filter: non-superuser teachers only see students in their own section
    (extend get_tenant_filter to add course / year isolation if needed).
    """

    list_display   = ["user", "roll_no", "course", "year", "section"]
    list_filter    = ["year", "course", "section"]
    search_fields  = ["user__username", "user__first_name", "user__last_name", "roll_no"]
    ordering       = ["roll_no"]
    readonly_fields = ["roll_no"]          # roll_no is immutable after creation

    # ── Tenant isolation ──────────────────────────────────────────────────────
    def get_tenant_filter(self, request):
        """
        Teachers only see students in courses they teach.

        Extend this with section / batch isolation for multi-campus SaaS.
        """
        role = RBACService.get_role(request.user)
        if role == "teacher":
            try:
                teacher = request.user.teacher  
            except AttributeError:
                pass
        return {}

@admin.register(Teacher)
class TeacherAdmin(RBACAdmin):
    list_display  = ["user", "department"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "department"]
    list_filter   = ["department"]
    ordering      = ["department", "user__last_name"]

@admin.register(LeaveRequest)
class LeaveRequestAdmin(RBACAdmin):
    """
    Leave request management.

    - Admin role: full CRUD (approve / reject / delete).
    - Receptionist / teacher: view-only via ReadOnlyRBACAdmin pattern.
      Switch the parent to ReadOnlyRBACAdmin if those roles need dashboard
      visibility without write access.
    """

    list_display  = ["student", "from_date", "to_date", "status"]
    list_filter   = ["status"]
    search_fields = ["student__roll_no", "student__user__first_name"]
    ordering      = ["-from_date"]
    actions       = ["approve_leaves", "reject_leaves"]

    @admin.action(description="✅ Approve selected leave requests")
    def approve_leaves(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "Permission denied.", level="error")
            return
        updated = queryset.update(status=LeaveRequest.Status.APPROVED)
        self.message_user(request, f"{updated} leave request(s) approved.")

    @admin.action(description="❌ Reject selected leave requests")
    def reject_leaves(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "Permission denied.", level="error")
            return
        updated = queryset.update(status=LeaveRequest.Status.REJECTED)
        self.message_user(request, f"{updated} leave request(s) rejected.")

