# fees/services.py
"""
Fees domain service layer.

RESPONSIBILITIES:
    FeeStructureService  — validate + create/update FeeStructure
    StudentFeeService    — generate bills, compute overdue status, sync payment status
    PaymentService       — submit payments, verify/reject, recompute bill status

RULES:
    - Views call services; serializers call services.
    - No model imports in views beyond what's needed for queryset.
    - All multi-model writes wrapped in transaction.atomic().
    - No Django request objects inside services (keep testable).
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import FeeStructure, StudentFee, Payment


# ─────────────────────────────────────────────────────────────────────────────
# FeeStructureService
# ─────────────────────────────────────────────────────────────────────────────

class FeeStructureService:

    @staticmethod
    def validate_unique(faculty, year, semester, exclude_pk=None) -> None:
        """
        Raises ValueError if a FeeStructure already exists for this
        (faculty, year, semester) triple. Called from serializer.validate().
        """
        qs = FeeStructure.objects.filter(
            faculty=faculty, year=year, semester=semester
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValueError(
                f"A fee structure for this faculty "
                f"(Year {year}, Semester {semester}) already exists."
            )

    @staticmethod
    def validate_fees_nonzero(tuition, exam, library, misc) -> None:
        """Raises ValueError if all fee components are zero."""
        total = (tuition or Decimal('0')) + (exam or Decimal('0')) + \
                (library or Decimal('0')) + (misc or Decimal('0'))
        if total <= Decimal('0'):
            raise ValueError(
                "At least one fee component must be greater than zero. "
                "A fee structure with all zeros is invalid."
            )

    @staticmethod
    def validate_due_date_not_past(due_date) -> None:
        """Raises ValueError if due_date is in the past (CREATE only)."""
        if due_date < timezone.now().date():
            raise ValueError(
                "Due date cannot be in the past when creating a new fee structure."
            )


# ─────────────────────────────────────────────────────────────────────────────
# StudentFeeService
# ─────────────────────────────────────────────────────────────────────────────

class StudentFeeService:

    @staticmethod
    def validate_no_duplicate_bill(student, fee_structure, exclude_pk=None) -> None:
        """Raises ValueError if a bill already exists for this student+plan."""
        qs = StudentFee.objects.filter(student=student, fee_structure=fee_structure)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValueError(
                "A fee bill for this student and fee structure already exists. "
                "Use the existing bill to record payments."
            )

    @staticmethod
    def validate_fee_structure_not_expired(fee_structure) -> None:
        """Raises ValueError if the fee plan's due date has passed."""
        if fee_structure and fee_structure.due_date < timezone.now().date():
            raise ValueError(
                "This fee structure's due date has already passed. "
                "Update the due date before generating new bills from it."
            )

    @staticmethod
    @transaction.atomic
    def generate_bill(student, fee_structure, due_date=None, remarks='') -> StudentFee:
        """
        Creates a StudentFee (bill) for a student.
        - total_amount is SNAPSHOTTED from fee_structure.total at generation time.
          If the fee plan changes later, existing bills are NOT retroactively altered.
        - status starts as PENDING.
        """
        StudentFeeService.validate_no_duplicate_bill(student, fee_structure)
        StudentFeeService.validate_fee_structure_not_expired(fee_structure)

        return StudentFee.objects.create(
            student       = student,
            fee_structure = fee_structure,
            total_amount  = fee_structure.total,     # snapshot
            status        = StudentFee.Status.PENDING,
            due_date      = due_date or fee_structure.due_date,
            remarks       = remarks,
        )

    @staticmethod
    def is_overdue(student_fee: StudentFee) -> bool:
        """True if unpaid/partial and past due date."""
        return (
            student_fee.status != StudentFee.Status.PAID
            and student_fee.due_date < timezone.now().date()
        )

    @staticmethod
    @transaction.atomic
    def recompute_status(student_fee: StudentFee) -> StudentFee:
        """
        Recalculates StudentFee.status and amount_paid based on
        all VERIFIED payments. Called after every payment verification.

        Status logic:
            amount_paid == 0              → PENDING
            0 < amount_paid < total       → PARTIAL
            amount_paid >= total          → PAID
        """
        verified_total = Payment.objects.filter(
            student_fee=student_fee,
            verification_status=Payment.VerificationStatus.VERIFIED,
        ).aggregate(
            total=__import__('django.db.models', fromlist=['Sum']).Sum('amount')
        )['total'] or Decimal('0.00')

        if verified_total <= Decimal('0'):
            new_status = StudentFee.Status.PENDING
        elif verified_total < student_fee.total_amount:
            new_status = StudentFee.Status.PARTIAL
        else:
            new_status = StudentFee.Status.PAID

        StudentFee.objects.filter(pk=student_fee.pk).update(
            amount_paid = verified_total,
            status      = new_status,
        )
        student_fee.refresh_from_db()
        return student_fee


# ─────────────────────────────────────────────────────────────────────────────
# PaymentService
# ─────────────────────────────────────────────────────────────────────────────

class PaymentService:

    @staticmethod
    def validate_bill_not_fully_paid(student_fee: StudentFee) -> None:
        """Raises ValueError if the bill is already PAID."""
        if student_fee.status == StudentFee.Status.PAID:
            raise ValueError(
                "This bill is already fully paid. No further payments accepted."
            )

    @staticmethod
    def validate_amount_vs_balance(amount: Decimal, student_fee: StudentFee) -> None:
        """Raises ValueError if payment amount exceeds remaining balance."""
        if amount > student_fee.balance_due:
            raise ValueError(
                f"Payment of Rs.{amount} exceeds the remaining "
                f"balance of Rs.{student_fee.balance_due}. "
                "Overpayment is not accepted."
            )

    @staticmethod
    def validate_screenshot_required(method: str, screenshot) -> None:
        """Raises ValueError if digital payment has no screenshot."""
        if method in {Payment.Method.QR, Payment.Method.BANK} and not screenshot:
            raise ValueError(
                f"A payment screenshot is required for "
                f"'{Payment.Method(method).label}' payments."
            )

    @staticmethod
    def validate_paid_at_not_future(paid_at) -> None:
        """Raises ValueError if paid_at is more than 1 hour in the future."""
        import datetime
        if paid_at > timezone.now() + datetime.timedelta(hours=1):
            raise ValueError("Payment date cannot be in the future.")

    @staticmethod
    @transaction.atomic
    def submit_payment(
        student_fee: StudentFee,
        amount: Decimal,
        payment_method: str,
        reference: str = '',
        screenshot=None,
        paid_at=None,
    ) -> Payment:
        """
        Creates a Payment record.
        Does NOT update StudentFee.status — that happens only when
        a payment is VERIFIED (via verify_payment).
        """
        PaymentService.validate_bill_not_fully_paid(student_fee)
        PaymentService.validate_amount_vs_balance(amount, student_fee)
        PaymentService.validate_screenshot_required(payment_method, screenshot)

        return Payment.objects.create(
            student_fee     = student_fee,
            amount          = amount,
            payment_method  = payment_method,
            reference       = reference,
            screenshot      = screenshot,
            paid_at         = paid_at or timezone.now(),
            verification_status = Payment.VerificationStatus.PENDING,
        )

    @staticmethod
    @transaction.atomic
    def verify_payment(
        payment: Payment,
        new_status: str,
        admin_note: str,
        verified_by,
    ) -> Payment:
        """
        Admin approves or rejects a PENDING payment.
        On VERIFIED: recalculates StudentFee.status via StudentFeeService.
        On REJECTED: no status change to StudentFee.

        Raises ValueError if payment is not PENDING, or if rejecting without a note.
        """
        if payment.verification_status != Payment.VerificationStatus.PENDING:
            raise ValueError(
                f"This payment is already "
                f"'{payment.get_verification_status_display()}'. "
                "Only pending payments can be verified or rejected."
            )
        if new_status == Payment.VerificationStatus.PENDING:
            raise ValueError(
                "You must choose 'verified' or 'rejected'. "
                "Setting status back to pending is not allowed."
            )
        if new_status == Payment.VerificationStatus.REJECTED and not admin_note.strip():
            raise ValueError(
                "A reason is required when rejecting a payment. "
                "The student needs to understand what went wrong."
            )

        Payment.objects.filter(pk=payment.pk).update(
            verification_status = new_status,
            admin_note          = admin_note,
            verified_by         = verified_by,
            verified_at         = timezone.now(),
        )
        payment.refresh_from_db()

        # Recompute bill status only after a verification decision
        if new_status == Payment.VerificationStatus.VERIFIED:
            StudentFeeService.recompute_status(payment.student_fee)

        return payment
