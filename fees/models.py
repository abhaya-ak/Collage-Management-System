import datetime
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


# ---------------------------------------------------------------------------
# FeeStructure
# ---------------------------------------------------------------------------

class FeeStructure(models.Model):
    """
    Fee template for a cohort (faculty + year + semester).
    """

    faculty = models.ForeignKey(          # was missing entirely
        "academics.Faculty",
        on_delete=models.PROTECT,
        related_name="fee_structures",
        null=True,                        # temporary - remove after migration
        blank=True,
    )
    year = models.PositiveSmallIntegerField(default=1)
    semester = models.PositiveSmallIntegerField(default=1)

    tuition_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    exam_fee          = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    library_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    miscellaneous_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Optional catch-all for small charges",
    )
    due_date = models.DateField(default=datetime.date(2025, 1, 1))

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = ("faculty", "year", "semester")
        ordering = ["faculty", "year", "semester"]

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


# ---------------------------------------------------------------------------
# StudentFee
# ---------------------------------------------------------------------------

class StudentFee(models.Model):
    """
    Individual bill generated for one student from a FeeStructure.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIAL = "partial", "Partially Paid"
        PAID    = "paid",    "Fully Paid"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="fees",
        null=True,                        # temporary - remove after migration
        blank=True,
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.PROTECT,
        related_name="student_fees",
        null=True,                        # temporary - remove after migration
        blank=True,
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0.00,                     # temporary - remove after migration
        help_text="Copied from FeeStructure.total at time of generation",
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
    due_date = models.DateField(
        default=datetime.date(2025, 1, 1),  # temporary - remove after migration
    )
    remarks = models.TextField(
        blank=True,
        help_text="Admin notes, e.g. scholarship waiver or late fine",
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        unique_together = ("student", "fee_structure")
        ordering = ["-created_at"]

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.amount_paid

    def __str__(self):
        return f"{self.student} | {self.fee_structure} | {self.status}"


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

def payment_screenshot_path(instance, filename):
    return f"payments/student_{instance.student_fee.student_id}/{filename}"


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

    student_fee = models.ForeignKey(
        StudentFee,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,                        # temporary - remove after migration
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0.00,                     # temporary - remove after migration
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

    paid_at = models.DateTimeField(
        default=datetime.datetime(2025, 1, 1),  # temporary - remove after migration
        help_text="When the student claims payment was made",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return (
            f"Payment Rs.{self.amount} | "
            f"{self.student_fee.student} | "
            f"{self.get_payment_method_display()} | "
            f"{self.verification_status}"
        )