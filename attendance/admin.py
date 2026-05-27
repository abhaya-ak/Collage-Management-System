# attendance/admin.py
"""
RBAC-aware admin for the attendance app.

Permission codes:
  attendance.view_attendance    → PermissionCodes.ATTENDANCE_VIEW_ALL
  attendance.mark_attendance    → PermissionCodes.ATTENDANCE_MARK  (add/change)
  attendance.delete_attendance  → auto-generated (restrict to admin/superuser)

Tenant filter: teachers only see attendance they marked;
               students only see their own records.
"""
from django.contrib import admin

from auth_core.admin_base import RBACAdmin
from auth_core.services.rbac_service import RBACService
from attendance.models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(RBACAdmin):
    """
    Attendance record management.

    The 'mark_attendance' permission is the canonical verb from PermissionCodes.
    We map it to add and change since both actions correspond to "marking".

    Permission codes:
      view   → attendance.view_attendance   (auto-generated)
      add    → attendance.mark_attendance   (custom verb)
      change → attendance.mark_attendance
      delete → attendance.delete_attendance (auto-generated; restrict if needed)
    """

    add_permission    = "attendance.mark_attendance"
    change_permission = "attendance.mark_attendance"

    list_display   = ["student", "subject", "date", "status", "marked_by", "created_at"]
    list_filter    = ["status", "date", "subject__name"]
    search_fields  = ["student__roll_no", "student__user__first_name", "subject__code"]
    ordering       = ["-date", "student"]
    readonly_fields = ["created_at"]
    date_hierarchy  = "date"

    def get_tenant_filter(self, request):
        """
        Row-level isolation by role:
          - teacher  → only records they personally marked
          - student  → only their own attendance records
          - admin    → all records (no filter)
        """
        role = RBACService.get_role(request.user)
        if role == "teacher":
            return {"marked_by": request.user}
        if role == "student":
            try:
                return {"student__user": request.user}
            except Exception:
                pass
        return {}
