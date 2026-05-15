from django.db import models
# 10) FeeStructure

from django.core.validators import MinValueValidator
from decimal import Decimal


class FeeStructure(models.Model):
    """
    The official fee template for a cohort (course + year + semester).
    Admin creates one of these; StudentFee rows are generated from it.
    """
    course = models.ForeignKey(
        "academics.Course",
        on_delete=models.PROTECT,
        related_name="fee_structures",
    )
    year = models.PositiveSmallIntegerField(help_text="Academic year, e.g. 1, 2, 3")
    semester = models.PositiveSmallIntegerField(help_text="Semester number, e.g. 1, 2")

    tuition_fee = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    exam_fee = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    library_fee = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    miscellaneous_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Optional catch-all for small charges",
    )

    due_date = models.DateField(help_text="Default due date for this fee plan")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Prevent duplicate plans for the same cohort
        unique_together = ("course", "year", "semester")
        ordering = ["course", "year", "semester"]

    @property
    def total(self) -> Decimal:
        """Sum of all fee components."""
        return self.tuition_fee + self.exam_fee + self.library_fee + self.miscellaneous_fee

    def __str__(self):
        return f"{self.course} | Year {self.year} Sem {self.semester}"


class StudentFee(models.Model):
    """
    The individual bill generated for one student from a FeeStructure.
    Tracks how much they owe and how much has been paid so far.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIAL = "partial", "Partially Paid"
        PAID = "paid", "Fully Paid"

    student = models.ForeignKey(
        "users.Student",
        on_delete=models.PROTECT,
        related_name="fees",
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.PROTECT,
        related_name="student_fees",
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Copied from FeeStructure.total at time of generation",
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Can override the structure's default due date per student if needed
    due_date = models.DateField()

    remarks = models.TextField(
        blank=True,
        help_text="Admin notes, e.g. scholarship waiver or late fine",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One bill per student per fee plan
        unique_together = ("student", "fee_structure")
        ordering = ["-created_at"]

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.amount_paid

    def recompute_status(self) -> None:
        """
        Call this after every payment to keep status in sync.
        Never update status manually — always go through here.
        """
        if self.amount_paid <= Decimal("0.00"):
            self.status = self.Status.PENDING
        elif self.amount_paid >= self.total_amount:
            self.status = self.Status.PAID
        else:
            self.status = self.Status.PARTIAL

    def __str__(self):
        return f"{self.student} | {self.fee_structure} | {self.status}"


def payment_screenshot_path(instance, filename):
    """
    Organise uploads by student so they don't pile into one flat folder.
    Result: media/payments/student_<id>/<filename>
    """
    return f"payments/student_{instance.student_fee.student_id}/{filename}"


class Payment(models.Model):
    """
    A single transaction record — one Payment row per payment event.
    Multiple Payment rows can satisfy one StudentFee.
    """

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        QR = "qr", "QR / eSewa / Khalti"
        BANK = "bank", "Bank Transfer"
        OTHER = "other", "Other"

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending Verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    student_fee = models.ForeignKey(
        StudentFee,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_method = models.CharField(
        max_length=10,
        choices=Method.choices,
        default=Method.CASH,
    )

    # For QR/bank: transaction ID, reference code, cheque number, etc.
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Transaction ID, cheque number, or any reference code",
    )

    # The screenshot upload — proof of payment
    screenshot = models.ImageField(
        upload_to=payment_screenshot_path,
        null=True,
        blank=True,
        help_text="Payment proof screenshot (required for QR/bank transfers)",
    )

    verification_status = models.CharField(
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verified_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_payments",
        help_text="Admin/staff who verified this payment",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    admin_note = models.TextField(
        blank=True,
        help_text="Reason for rejection or verification note",
    )

    paid_at = models.DateTimeField(help_text="When the student claims payment was made")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return (
            f"Payment ₨{self.amount} | {self.student_fee.student} "
            f"| {self.get_payment_method_display()} | {self.verification_status}"
        )