# fees/serializers.py
import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import FeeStructure, StudentFee, Payment


# ===========================================================================
# HELPERS
# ===========================================================================

class _DecimalField(serializers.DecimalField):
    """Shared config for all money fields — 10 digits, 2 decimal places."""
    def __init__(self, **kwargs):
        kwargs.setdefault('max_digits',    10)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('coerce_to_string', False)  # send as number, not string
        super().__init__(**kwargs)


# ===========================================================================
# FEE STRUCTURE
# ===========================================================================

class FeeStructureReadSerializer(serializers.ModelSerializer):
    """
    What anyone sees when viewing a fee plan.
    Resolves FK to human label. Exposes computed total.
    """
    faculty_name = serializers.CharField(
        source='faculty.name', read_only=True
    )
    faculty_code = serializers.CharField(
        source='faculty.code', read_only=True
    )
    total = _DecimalField(read_only=True)   # model @property

    class Meta:
        model  = FeeStructure
        fields = [
            'id',
            'faculty', 'faculty_name', 'faculty_code',
            'year', 'semester',
            'tuition_fee', 'exam_fee', 'library_fee', 'miscellaneous_fee',
            'total',        # computed — sum of the four above
            'due_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class FeeStructureWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a fee plan.
    Validates: at least one fee > 0, sensible year/semester, due date
    not in the past, and uniqueness with a clear error message.
    """

    class Meta:
        model  = FeeStructure
        fields = [
            'id',
            'faculty', 'year', 'semester',
            'tuition_fee', 'exam_fee', 'library_fee', 'miscellaneous_fee',
            'due_date',
        ]
        read_only_fields = ['id']

    # --- Field-level -------------------------------------------------------

    def validate_year(self, value):
        if not (1 <= value <= 6):
            raise serializers.ValidationError(
                "Year must be between 1 and 6."
            )
        return value

    def validate_semester(self, value):
        if not (1 <= value <= 6):
            raise serializers.ValidationError(
                "Semester must be between 1 and 6."
            )
        return value

    def validate_due_date(self, value):
        # Allow past dates on UPDATE (admin correcting data).
        # Block only on CREATE to prevent accidental stale bills.
        if not self.instance and value < timezone.now().date():
            raise serializers.ValidationError(
                "Due date cannot be in the past when creating a new fee structure."
            )
        return value

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        self._validate_at_least_one_fee(attrs)
        self._validate_unique_together(attrs)
        return attrs

    def _validate_at_least_one_fee(self, attrs):
        fee_fields = ['tuition_fee', 'exam_fee', 'library_fee', 'miscellaneous_fee']
        total = sum(
            attrs.get(f, getattr(self.instance, f, Decimal('0.00')) or Decimal('0.00'))
            for f in fee_fields
        )
        if total <= Decimal('0.00'):
            raise serializers.ValidationError(
                "At least one fee component must be greater than zero. "
                "A fee structure with all zeros is invalid."
            )

    def _validate_unique_together(self, attrs):
        """
        Re-implement unique_together check here to return a clean API error
        instead of a raw DB IntegrityError.
        """
        faculty   = attrs.get('faculty',  getattr(self.instance, 'faculty',  None))
        year      = attrs.get('year',     getattr(self.instance, 'year',     None))
        semester  = attrs.get('semester', getattr(self.instance, 'semester', None))

        qs = FeeStructure.objects.filter(
            faculty=faculty, year=year, semester=semester
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                f"A fee structure for this faculty (Year {year}, "
                f"Semester {semester}) already exists."
            )

    def to_representation(self, instance):
        return FeeStructureReadSerializer(instance, context=self.context).data


# ===========================================================================
# STUDENT FEE
# ===========================================================================

class StudentFeeReadSerializer(serializers.ModelSerializer):
    """
    Full bill view. Nested fee plan + all payment attempts.
    Used by both student (own bill) and admin (any bill).
    """
    fee_structure  = FeeStructureReadSerializer(read_only=True)
    payments       = serializers.SerializerMethodField()
    balance_due    = _DecimalField(read_only=True)   # model @property
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    student_name   = serializers.SerializerMethodField()
    student_roll   = serializers.CharField(
        source='student.roll_no', read_only=True
    )
    is_overdue     = serializers.SerializerMethodField()

    class Meta:
        model  = StudentFee
        fields = [
            'id',
            'student', 'student_name', 'student_roll',
            'fee_structure',
            'total_amount', 'amount_paid', 'balance_due',
            'status', 'status_display',
            'due_date', 'is_overdue',
            'remarks',
            'payments',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return f"{u.first_name} {u.last_name}".strip()

    def get_is_overdue(self, obj):
        """
        True if unpaid/partially paid AND past due date.
        Computed here — no separate DB field needed.
        """
        return (
            obj.status != StudentFee.Status.PAID
            and obj.due_date < timezone.now().date()
        )

    def get_payments(self, obj):
        """
        Inline all payments. Avoids a second API round-trip on the bill screen.
        """
        return PaymentSummarySerializer(
            obj.payments.all(), many=True, context=self.context
        ).data


class StudentFeeGenerateSerializer(serializers.ModelSerializer):
    """
    Admin generates a bill for a student from a FeeStructure.
    total_amount is auto-copied from fee_structure.total — admin cannot
    set it manually to prevent data divergence from the fee plan.
    """

    class Meta:
        model  = StudentFee
        fields = [
            'id',
            'student',
            'fee_structure',
            'due_date',
            'remarks',
        ]
        read_only_fields = ['id']

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        self._validate_unique_bill(attrs)
        self._validate_fee_structure_active(attrs)
        return attrs

    def _validate_unique_bill(self, attrs):
        student       = attrs.get('student',       getattr(self.instance, 'student',       None))
        fee_structure = attrs.get('fee_structure', getattr(self.instance, 'fee_structure', None))

        qs = StudentFee.objects.filter(student=student, fee_structure=fee_structure)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A fee bill for this student and fee structure already exists. "
                "Use the existing bill to record payments."
            )

    def _validate_fee_structure_active(self, attrs):
        fee_structure = attrs.get('fee_structure', getattr(self.instance, 'fee_structure', None))
        if fee_structure and fee_structure.due_date < timezone.now().date():
            raise serializers.ValidationError({
                'fee_structure': (
                    "This fee structure's due date has already passed. "
                    "Update the due date before generating new bills from it."
                )
            })

    def save(self, **kwargs):
        """
        Auto-copy total_amount from the fee plan at time of generation.
        This snapshot is intentional — if the plan changes later, existing
        bills are not retroactively altered (audit trail preserved).
        """
        fee_structure = self.validated_data.get(
            'fee_structure',
            getattr(self.instance, 'fee_structure', None)
        )
        kwargs['total_amount'] = fee_structure.total
        kwargs['status']       = StudentFee.Status.PENDING
        return super().save(**kwargs)

    def to_representation(self, instance):
        return StudentFeeReadSerializer(instance, context=self.context).data


# ===========================================================================
# PAYMENT — lightweight summary (nested inside StudentFee)
# ===========================================================================

class PaymentSummarySerializer(serializers.ModelSerializer):
    """
    Compact read-only view embedded inside the bill.
    Excludes admin-only fields (admin_note, verified_by detail).
    """
    payment_method_display      = serializers.CharField(
        source='get_payment_method_display',      read_only=True
    )
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )

    class Meta:
        model  = Payment
        fields = [
            'id',
            'amount',
            'payment_method', 'payment_method_display',
            'reference',
            'screenshot',
            'verification_status', 'verification_status_display',
            'paid_at',
            'created_at',
        ]
        read_only_fields = fields


# ===========================================================================
# PAYMENT — student submits proof
# ===========================================================================

class PaymentCreateSerializer(serializers.ModelSerializer):
    """
    Student submits a payment.
    Enforces: amount ≤ balance, screenshot for digital, no double-paying.
    verified_by / verified_at / verification_status are NEVER accepted here.
    """

    class Meta:
        model  = Payment
        fields = [
            'id',
            'student_fee',
            'amount',
            'payment_method',
            'reference',
            'screenshot',
            'paid_at',
        ]
        read_only_fields = ['id']

    # --- Field-level -------------------------------------------------------

    def validate_student_fee(self, student_fee):
        if student_fee.status == StudentFee.Status.PAID:
            raise serializers.ValidationError(
                "This bill is already fully paid. No further payments accepted."
            )
        return student_fee

    def validate_paid_at(self, value):
        """
        Student cannot claim payment was made in the future.
        A little leeway (1 hour) for timezone edge cases.
        """
        if value > timezone.now() + datetime.timedelta(hours=1):
            raise serializers.ValidationError(
                "Payment date cannot be in the future."
            )
        return value

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        self._validate_amount_vs_balance(attrs)
        self._validate_screenshot_required(attrs)
        return attrs

    def _validate_amount_vs_balance(self, attrs):
        student_fee = attrs.get('student_fee')
        amount      = attrs.get('amount')

        if student_fee and amount:
            if amount > student_fee.balance_due:
                raise serializers.ValidationError({
                    'amount': (
                        f"Payment of Rs.{amount} exceeds the remaining "
                        f"balance of Rs.{student_fee.balance_due}. "
                        "Overpayment is not accepted."
                    )
                })

    def _validate_screenshot_required(self, attrs):
        method     = attrs.get('payment_method', Payment.Method.CASH)
        screenshot = attrs.get('screenshot')

        if method in {Payment.Method.QR, Payment.Method.BANK} and not screenshot:
            raise serializers.ValidationError({
                'screenshot': (
                    f"A payment screenshot is required for "
                    f"'{Payment.Method(method).label}' payments."
                )
            })

    def to_representation(self, instance):
        return PaymentSummarySerializer(instance, context=self.context).data


# ===========================================================================
# PAYMENT — admin verifies or rejects
# ===========================================================================

class PaymentVerifySerializer(serializers.ModelSerializer):
    """
    Admin approves or rejects a PENDING payment.
    verified_by and verified_at are set by the view — not accepted from input.

    After save(), the view must call _recompute_student_fee_status()
    to keep StudentFee.status in sync.
    """

    class Meta:
        model  = Payment
        fields = ['id', 'verification_status', 'admin_note']
        read_only_fields = ['id']

    # --- Field-level -------------------------------------------------------

    def validate_verification_status(self, value):
        """Only PENDING payments can be processed here."""
        if self.instance and self.instance.verification_status != Payment.VerificationStatus.PENDING:
            raise serializers.ValidationError(
                f"This payment is already '{self.instance.get_verification_status_display()}'. "
                "Only pending payments can be verified or rejected."
            )
        if value == Payment.VerificationStatus.PENDING:
            raise serializers.ValidationError(
                "You must choose 'verified' or 'rejected'. "
                "Setting status back to pending is not allowed here."
            )
        return value

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        status = attrs.get(
            'verification_status',
            getattr(self.instance, 'verification_status', None)
        )
        note = attrs.get('admin_note', '').strip()

        if status == Payment.VerificationStatus.REJECTED and not note:
            raise serializers.ValidationError({
                'admin_note': (
                    "A reason is required when rejecting a payment. "
                    "The student needs to understand what went wrong."
                )
            })
        return attrs

    def to_representation(self, instance):
        return PaymentAdminDetailSerializer(instance, context=self.context).data


# ===========================================================================
# PAYMENT — full admin read
# ===========================================================================

class PaymentAdminDetailSerializer(serializers.ModelSerializer):
    """
    Complete payment record for admin review screens and audit trail.
    All fields visible. verified_by resolved to username.
    """
    payment_method_display      = serializers.CharField(
        source='get_payment_method_display',      read_only=True
    )
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True
    )
    verified_by_username = serializers.SerializerMethodField()
    student_roll         = serializers.CharField(
        source='student_fee.student.roll_no', read_only=True
    )
    student_name         = serializers.SerializerMethodField()

    class Meta:
        model  = Payment
        fields = [
            'id',
            'student_roll', 'student_name',
            'student_fee',
            'amount',
            'payment_method', 'payment_method_display',
            'reference',
            'screenshot',
            'verification_status', 'verification_status_display',
            'verified_by', 'verified_by_username',
            'verified_at',
            'admin_note',
            'paid_at',
            'created_at',
        ]
        read_only_fields = fields

    def get_verified_by_username(self, obj):
        return obj.verified_by.username if obj.verified_by else None

    def get_student_name(self, obj):
        u = obj.student_fee.student.user
        return f"{u.first_name} {u.last_name}".strip()