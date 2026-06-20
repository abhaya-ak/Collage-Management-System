"""
Sprint 10 — Fees domain (models).

Three layered concepts (this sprint builds the first two):
    FeeStructure  -> the template: "BCA Semester 1 costs Rs. 50,000"
    FeeComponent  -> line items:   Admission / Tuition / Library / Exam ...
    (StudentFee, Payment, Receipt come next.)

`FeeStructure.total_amount` is stored (denormalized for querying + later
snapshotting onto StudentFee) but the FeeComponents are the source of truth.
The service layer keeps total_amount == components_total; the model exposes
`components_total` so the stored value can always be verified.
"""

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.academics.models import AcademicYear, Program, Semester
from apps.core.enums import FeeStatus, PaymentMethod
from apps.core.models import BaseModel, SoftDeleteMixin
from apps.students.models import Student


class FeeStructure(BaseModel, SoftDeleteMixin):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="fee_structures"
    )
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="fee_structures"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="fee_structures"
    )
    name = models.CharField(max_length=150)  # e.g. "BCA Sem 1 Fee"
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fee Structure"
        verbose_name_plural = "Fee Structures"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "program", "semester", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_fee_structure",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.program.code} Sem{self.semester.number})"

    @property
    def components_total(self):
        """Authoritative sum of this structure's (non-deleted) components."""
        agg = self.components.aggregate(total=Sum("amount"))
        return agg["total"] or 0


class FeeComponent(BaseModel, SoftDeleteMixin):
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.CASCADE, related_name="components"
    )
    name = models.CharField(max_length=100)  # e.g. "Tuition Fee"
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_optional = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Fee Component"
        verbose_name_plural = "Fee Components"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["fee_structure", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_component_per_structure",
            )
        ]

    def __str__(self):
        return f"{self.name}: {self.amount}"


# =============================================================
# StudentFee — "Student X owes amount Y"
# =============================================================
class StudentFee(BaseModel, SoftDeleteMixin):
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="fees"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="student_fees"
    )
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="student_fees"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="student_fees"
    )
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.PROTECT, related_name="student_fees"
    )

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    scholarship_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(
        max_length=20, choices=FeeStatus.choices, default=FeeStatus.PENDING
    )
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Student Fee"
        verbose_name_plural = "Student Fees"
        ordering = ["-created_at"]
        constraints = [
            # One fee record per student per term.
            models.UniqueConstraint(
                fields=["student", "academic_year", "program", "semester"],
                condition=models.Q(is_deleted=False),
                name="unique_student_fee_per_term",
            )
        ]

    def __str__(self):
        return f"{self.student.student_id} owes {self.due_amount} [{self.status}]"

    @property
    def payable_amount(self):
        """Net charge after discount + scholarship (before payments)."""
        return self.total_amount - self.discount_amount - self.scholarship_amount

    @property
    def computed_due(self):
        """Authoritative outstanding balance = payable - paid (never below 0)."""
        return max(self.payable_amount - self.paid_amount, 0)


# =============================================================
# Payment — one payment transaction against a StudentFee
# =============================================================
class Payment(BaseModel, SoftDeleteMixin):
    student_fee = models.ForeignKey(
        StudentFee, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference_number = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments_collected",
    )
    paid_at = models.DateTimeField(default=timezone.now)

    # Refund tracking — a refunded payment is excluded from the paid total but
    # the record (and its receipt) are kept for audit.
    is_refunded = models.BooleanField(default=False)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments_refunded",
    )
    refund_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.amount} via {self.payment_method} for {self.student_fee.student.student_id}"


# =============================================================
# Receipt — one per Payment (number generated in the service layer)
# =============================================================
class Receipt(BaseModel, SoftDeleteMixin):
    payment = models.OneToOneField(
        Payment, on_delete=models.PROTECT, related_name="receipt"
    )
    receipt_number = models.CharField(max_length=30, unique=True)  # RCT-YYYY-XXXX
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    generated_at = models.DateTimeField(default=timezone.now)
    pdf_path = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"
        ordering = ["-generated_at"]

    def __str__(self):
        return self.receipt_number
