# feedback/admin.py
from django.contrib import admin
from auth_core.admin_base import RBACAdmin
from auth_core.services.rbac_service import RBACService
from feedback.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(RBACAdmin):
    """
    Feedback management for admin review and reply workflow.

    add is disabled — feedback must be submitted via the API by students.

    Permission codes:
      view   → feedback.view_feedback    (auto-generated; maps to FEEDBACK_VIEW_ALL)
      add    → blocked (returns False always — API only)
      change → feedback.change_feedback  (auto-generated; for reply / status update)
      delete → feedback.delete_feedback  (auto-generated)
    """

    add_permission = None   # triggers auto-generation but we override has_add_permission

    list_display   = ["student", "type", "target_teacher", "status", "submitted_at", "replied_at"]
    list_filter    = ["type", "status"]
    search_fields  = ["student__roll_no", "student__user__first_name", "message"]
    ordering       = ["-submitted_at"]
    readonly_fields = ["student", "type", "message", "submitted_at", "target_teacher"]

    def has_add_permission(self, request):
        """Feedback must always be submitted via the API, not the admin."""
        return False

    def get_tenant_filter(self, request):
        """
        Teachers only see feedback directed at them.
        Admin sees all feedback.
        """
        role = RBACService.get_role(request.user)
        if role == "teacher":
            return {"target_teacher": request.user}
        return {}

    def save_model(self, request, obj, form, change):
        """
        Auto-stamp replied_by and replied_at when admin_reply is set for the
        first time.
        """
        from django.utils import timezone
        if change and obj.admin_reply and not obj.replied_at:
            obj.replied_by = request.user
            obj.replied_at = timezone.now()
        super().save_model(request, obj, form, change)
