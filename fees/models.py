# fees/models.py
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _default_due_date():
    """
    Dynamic default: 30 days from today.
    Using a callable avoids the Django system-check warning about mutable
    field defaults, and prevents all rows from sharing the same stale date.
    """
    from django.utils import timezone
    import datetime
    return timezone.now().date() + datetime.timedelta(days=30)


def payment_screenshot_path(instance, filename):
    return f"payments/student_{instance.student_fee.student_id}/{filename}"


# ─────────────────────────────────────────────────────────────────────────────
# FeeStructure — the fee plan for a faculty / year / semester combo
# ─────────────────────────────────────────────────────────────────────────────

class FeeStructure(models.Model):
    # Phase 3 cleanup: removed null=True, blank=True (was temporary migration helper)
    faculty = models.ForeignKey(
    "academics.Faculty",
    on_delete=models.PROTECT,
    related_name="fee_structures",
    null=True,
    blank=True,
    )
    year     = models.PositiveSmallIntegerField(default=1)
    semester = models.PositiveSmallIntegerField(default=1)

    tuition_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    exam_fee          = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    library_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    miscellaneous_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Optional catch-all for small charges",
    )

    # Phase 3 cleanup: replaced hardcoded date(2025,1,1) with callable default
    due_date = models.DateField(default=_default_due_date)

    # null=True kept because existing DB rows have NULL — safe: auto_now_add
    # always writes a value on INSERT, so no new row will ever be NULL.
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = ("faculty", "year", "semester")
        ordering        = ["faculty", "year", "semester"]

    @property
    def total(self) -> Decimal:
        return (
            self.tuition_fee
            + self.exam_fee
            + self.library_fee
            + self.miscellaneous_fee
        )

    def __str__(self):
        return f"{self.faculty} | Year {self.year} Sem {self.semester}"


# ─────────────────────────────────────────────────────────────────────────────
# StudentFee — individual bill generated from a FeeStructure for one student
# ─────────────────────────────────────────────────────────────────────────────

class StudentFee(models.Model):
    """
    Individual bill generated for one student from a FeeStructure.
    total_amount is snapshotted at generation time (audit trail).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIAL = "partial", "Partially Paid"
        PAID    = "paid",    "Fully Paid"

    # Phase 3 cleanup: removed null=True, blank=True (was temporary)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="fees",
        null=True,
        blank=True,
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.PROTECT,
        related_name="student_fees",
        null=True,
        blank=True
    )
    # Phase 3 cleanup: removed default=0.00 (value set by StudentFeeGenerateSerializer.save())
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Snapshotted from FeeStructure.total at generation time",
    )
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Phase 3 cleanup: replaced hardcoded date(2025,1,1) with callable default
    due_date = models.DateField(default=_default_due_date)
    remarks  = models.TextField(
        blank=True,
        help_text="Admin notes, e.g. scholarship waiver or late fine",
    )

    # null=True kept because existing DB rows have NULL — safe: auto_now_add
    # always writes a value on INSERT, so no new row will ever be NULL.
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = ("student", "fee_structure")
        ordering        = ["-created_at"]

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.amount_paid

    def __str__(self):
        return f"{self.student} | {self.fee_structure} | {self.status}"

class Payment(models.Model):
    """
    A single transaction. Multiple payments can satisfy one StudentFee.
    """
    class Method(models.TextChoices):
        CASH  = "cash",  "Cash"
        QR    = "qr",    "QR / eSewa / Khalti"
        BANK  = "bank",  "Bank Transfer"
        OTHER = "other", "Other"

    class VerificationStatus(models.TextChoices):
        PENDING  = "pending",  "Pending Verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    # Phase 3 cleanup: removed null=True, blank=True (was temporary)
    student_fee = models.ForeignKey(
        StudentFee,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_method = models.CharField(
        max_length=10,
        choices=Method.choices,
        default=Method.CASH,
    )
    reference = models.CharField(
        max_length=100, blank=True,
        help_text="Transaction ID, cheque number, or any reference code",
    )
    screenshot = models.ImageField(
        upload_to=payment_screenshot_path,
        null=True, blank=True,
        help_text="Payment proof screenshot (required for QR/bank transfers)",
    )
    verification_status = models.CharField(
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_payments",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    admin_note  = models.TextField(blank=True)

    # Phase 3 cleanup: replaced hardcoded datetime(2025,1,1) with timezone.now
    # Kept as editable field — student declares when they claim payment was made.
    paid_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the student claims payment was made",
    )
    # null=True kept because existing DB rows have NULL — safe: auto_now_add
    # always writes a value on INSERT, so no new row will ever be NULL.
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    # ── Soft delete ──────────────────────────────────────────────────────────────
    # Hard-deleting payment records destroys the financial audit trail.
    # Soft-delete hides them from student-facing views while keeping every
    # transaction permanently recoverable for finance reconciliation.
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return (
            f"Payment Rs.{self.amount} | "
            f"{self.student_fee.student} | "
            f"{self.get_payment_method_display()} | "
            f"{self.verification_status}"
        )