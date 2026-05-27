# fees/admin.py
"""
RBAC-aware admin for the fees app.

Permission mapping (from PermissionCodes in users/constants.py):
  fees.view_feestructure      → fees.view_all_fees  (alias below)
  fees.manage_feestructure    → fees.manage_fees
  fees.view_studentfee        → fees.view_all_fees
  fees.manage_studentfee      → fees.manage_fees
  fees.view_payment           → fees.view_all_fees
  fees.verify_payment         → fees.verify_payment  (custom action verb)

Design decision: 'accounts' and 'finance' roles should see fees read-only.
The accounts role can also verify payments.  We use ReadOnlyRBACAdmin as the
base for PaymentAdmin and override just has_change_permission for the
'verify' action.
"""
from django.contrib import admin

from auth_core.admin_base import RBACAdmin, ReadOnlyRBACAdmin
from auth_core.services.rbac_service import RBACService
from fees.models import FeeStructure, StudentFee, Payment


# ─────────────────────────────────────────────────────────────────────────────
# FeeStructureAdmin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(FeeStructure)
class FeeStructureAdmin(RBACAdmin):
    """
    Manage fee plans per faculty / year / semester.

    Permission codes:
      view   → fees.view_feestructure  (auto-generated)
      add    → fees.manage_fees        (custom verb — broader than 'add')
      change → fees.manage_fees
      delete → fees.manage_fees
    """

    add_permission    = "fees.manage_fees"
    change_permission = "fees.manage_fees"
    delete_permission = "fees.manage_fees"

    list_display   = ["faculty", "year", "semester", "tuition_fee", "exam_fee", "library_fee",
                      "miscellaneous_fee", "due_date", "total_display"]
    list_filter    = ["faculty", "year", "semester"]
    search_fields  = ["faculty__name"]
    ordering       = ["faculty", "year", "semester"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="Total (Rs.)")
    def total_display(self, obj):
        return f"Rs. {obj.total:,.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# StudentFeeAdmin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(StudentFee)
class StudentFeeAdmin(RBACAdmin):
    """
    Individual student fee bills.

    Accounts role can view all; only admin/superuser should modify totals.

    Permission codes:
      view   → fees.view_studentfee   (auto-generated)
      add    → fees.manage_fees
      change → fees.manage_fees
      delete → fees.manage_fees
    """

    add_permission    = "fees.manage_fees"
    change_permission = "fees.manage_fees"
    delete_permission = "fees.manage_fees"

    list_display   = ["student", "fee_structure", "total_amount", "amount_paid",
                      "status", "due_date", "balance_display"]
    list_filter    = ["status", "fee_structure__year", "fee_structure__semester"]
    search_fields  = ["student__roll_no", "student__user__first_name", "student__user__last_name"]
    ordering       = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="Balance Due (Rs.)")
    def balance_display(self, obj):
        balance = obj.balance_due
        return f"Rs. {balance:,.2f}"

    def get_tenant_filter(self, request):
        """Students only see their own fee record."""
        role = RBACService.get_role(request.user)
        if role == "student":
            try:
                return {"student__user": request.user}
            except Exception:
                pass
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# PaymentAdmin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Payment)
class PaymentAdmin(RBACAdmin):
    """
    Payment records. Accounts role can view + verify; cannot create or delete.

    We override has_add_permission and has_delete_permission with tighter
    checks: only users with 'fees.manage_fees' can add/delete.
    The 'verify' action requires 'fees.verify_payment'.

    Permission codes:
      view   → fees.view_payment      (auto-generated)
      add    → fees.manage_fees       (admin only)
      change → fees.verify_payment    (accounts role)
      delete → fees.manage_fees       (admin only)
    """

    add_permission    = "fees.manage_fees"
    change_permission = "fees.verify_payment"
    delete_permission = "fees.manage_fees"

    list_display   = ["student_fee", "amount", "payment_method", "verification_status",
                      "verified_by", "paid_at", "created_at"]
    list_filter    = ["verification_status", "payment_method"]
    search_fields  = ["student_fee__student__roll_no", "reference"]
    ordering       = ["-paid_at"]
    readonly_fields = ["paid_at", "created_at", "screenshot"]
    actions        = ["verify_payments", "reject_payments"]

    @admin.action(description="✅ Verify selected payments")
    def verify_payments(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "Permission denied.", level="error")
            return
        from django.utils import timezone
        updated = queryset.update(
            verification_status=Payment.VerificationStatus.VERIFIED,
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        self.message_user(request, f"{updated} payment(s) verified.")

    @admin.action(description="❌ Reject selected payments")
    def reject_payments(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "Permission denied.", level="error")
            return
        updated = queryset.update(
            verification_status=Payment.VerificationStatus.REJECTED,
        )
        self.message_user(request, f"{updated} payment(s) rejected.")
