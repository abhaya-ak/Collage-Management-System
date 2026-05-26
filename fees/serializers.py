from django.utils import timezone
from rest_framework import serializers

from .models import FeeStructure, StudentFee, Payment
from .services import FeeStructureService, StudentFeeService, PaymentService


class _DecimalField(serializers.DecimalField):
    """Shared config for all money fields."""
    def __init__(self, **kwargs):
        kwargs.setdefault('max_digits', 10)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('coerce_to_string', False)
        super().__init__(**kwargs)

# FEE STRUCTURE

class FeeStructureReadSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    total        = _DecimalField(read_only=True)  # model @property

    class Meta:
        model  = FeeStructure
        fields = [
            'id',
            'faculty', 'faculty_name',
            'year', 'semester',
            'tuition_fee', 'exam_fee', 'library_fee', 'miscellaneous_fee',
            'total',
            'due_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class FeeStructureWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates / updates a fee plan.
    Validation rules delegated to FeeStructureService.
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

    # ── Field-level: format / range checks only ─────────────────────────────

    def validate_year(self, value):
        if not (1 <= value <= 6):
            raise serializers.ValidationError("Year must be between 1 and 6.")
        return value

    def validate_semester(self, value):
        if not (1 <= value <= 6):
            raise serializers.ValidationError("Semester must be between 1 and 6.")
        return value

    def validate_due_date(self, value):
        if not self.instance:  # CREATE only
            try:
                FeeStructureService.validate_due_date_not_past(value)
            except ValueError as e:
                raise serializers.ValidationError(str(e))
        return value

    def validate(self, attrs):
        # Resolve partial-update values
        def _get(field):
            return attrs.get(field, getattr(self.instance, field, None))

        try:
            FeeStructureService.validate_fees_nonzero(
                _get('tuition_fee'), _get('exam_fee'),
                _get('library_fee'), _get('miscellaneous_fee'),
            )
            FeeStructureService.validate_unique(
                faculty   = _get('faculty'),
                year      = _get('year'),
                semester  = _get('semester'),
                exclude_pk = self.instance.pk if self.instance else None,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def to_representation(self, instance):
        return FeeStructureReadSerializer(instance, context=self.context).data


# STUDENT FEE (BILL)

class StudentFeeReadSerializer(serializers.ModelSerializer):
    fee_structure  = FeeStructureReadSerializer(read_only=True)
    payments       = serializers.SerializerMethodField()
    balance_due    = _DecimalField(read_only=True)  # model @property
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    student_name   = serializers.SerializerMethodField()
    student_roll   = serializers.CharField(source='student.roll_no', read_only=True)
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
        # Delegated to service — serializer just calls it
        return StudentFeeService.is_overdue(obj)

    def get_payments(self, obj):
        return PaymentSummarySerializer(
            obj.payments.all(), many=True, context=self.context
        ).data


class StudentFeeGenerateSerializer(serializers.Serializer):
    """
    Admin generates a bill. Input-only — calls StudentFeeService.generate_bill().
    No ModelSerializer: total_amount is NEVER accepted from input.
    """
    student       = serializers.PrimaryKeyRelatedField(
        queryset=__import__('students.models', fromlist=['Student']).Student.objects.all()
    )
    fee_structure = serializers.PrimaryKeyRelatedField(
        queryset=FeeStructure.objects.all()
    )
    due_date      = serializers.DateField(required=False)
    remarks       = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, attrs):
        try:
            StudentFeeService.validate_no_duplicate_bill(
                student       = attrs['student'],
                fee_structure = attrs['fee_structure'],
            )
            StudentFeeService.validate_fee_structure_not_expired(attrs['fee_structure'])
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def save(self, **kwargs) -> StudentFee:
        """Delegates creation to service. Returns the created StudentFee."""
        return StudentFeeService.generate_bill(
            student       = self.validated_data['student'],
            fee_structure = self.validated_data['fee_structure'],
            due_date      = self.validated_data.get('due_date'),
            remarks       = self.validated_data.get('remarks', ''),
        )

    def to_representation(self, instance):
        return StudentFeeReadSerializer(instance, context=self.context).data


# PAYMENT

class PaymentSummarySerializer(serializers.ModelSerializer):
    """Compact read-only view embedded inside the bill."""
    payment_method_display      = serializers.CharField(
        source='get_payment_method_display',      read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True)

    class Meta:
        model  = Payment
        fields = [
            'id',
            'amount',
            'payment_method', 'payment_method_display',
            'reference', 'screenshot',
            'verification_status', 'verification_status_display',
            'paid_at', 'created_at',
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    """
    Student submits a payment. Calls PaymentService.submit_payment().
    verification fields are NEVER accepted here.
    """
    student_fee    = serializers.PrimaryKeyRelatedField(
        queryset=StudentFee.objects.all()
    )
    amount         = _DecimalField()
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference      = serializers.CharField(required=False, default='', allow_blank=True)
    screenshot     = serializers.ImageField(required=False, allow_null=True)
    paid_at        = serializers.DateTimeField(required=False, default=timezone.now)

    def validate_paid_at(self, value):
        try:
            PaymentService.validate_paid_at_not_future(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate(self, attrs):
        try:
            PaymentService.validate_bill_not_fully_paid(attrs['student_fee'])
            PaymentService.validate_amount_vs_balance(attrs['amount'], attrs['student_fee'])
            PaymentService.validate_screenshot_required(
                attrs.get('payment_method', Payment.Method.CASH),
                attrs.get('screenshot'),
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def save(self, **kwargs) -> Payment:
        return PaymentService.submit_payment(
            student_fee    = self.validated_data['student_fee'],
            amount         = self.validated_data['amount'],
            payment_method = self.validated_data['payment_method'],
            reference      = self.validated_data.get('reference', ''),
            screenshot     = self.validated_data.get('screenshot'),
            paid_at        = self.validated_data.get('paid_at'),
        )

    def to_representation(self, instance):
        return PaymentSummarySerializer(instance, context=self.context).data


class PaymentVerifySerializer(serializers.Serializer):
    """
    Admin approves or rejects a PENDING payment.
    Calls PaymentService.verify_payment() which also recomputes StudentFee.status.
    """
    verification_status = serializers.ChoiceField(choices=Payment.VerificationStatus.choices)
    admin_note          = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, attrs):
        try:
            # Stateless pre-check — full enforcement happens inside the service
            if attrs.get('verification_status') == Payment.VerificationStatus.PENDING:
                raise ValueError(
                    "You must choose 'verified' or 'rejected'. "
                    "Setting status back to pending is not allowed."
                )
            if (
                attrs.get('verification_status') == Payment.VerificationStatus.REJECTED
                and not attrs.get('admin_note', '').strip()
            ):
                raise ValueError(
                    "A reason is required when rejecting a payment."
                )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def to_representation(self, instance):
        return PaymentAdminDetailSerializer(instance, context=self.context).data


class PaymentAdminDetailSerializer(serializers.ModelSerializer):
    """Full payment record for admin review and audit trail."""
    payment_method_display      = serializers.CharField(
        source='get_payment_method_display',      read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', read_only=True)
    verified_by_username = serializers.SerializerMethodField()
    student_roll         = serializers.CharField(
        source='student_fee.student.roll_no', read_only=True)
    student_name         = serializers.SerializerMethodField()

    class Meta:
        model  = Payment
        fields = [
            'id',
            'student_roll', 'student_name',
            'student_fee',
            'amount',
            'payment_method', 'payment_method_display',
            'reference', 'screenshot',
            'verification_status', 'verification_status_display',
            'verified_by', 'verified_by_username',
            'verified_at', 'admin_note',
            'paid_at', 'created_at',
        ]
        read_only_fields = fields

    def get_verified_by_username(self, obj):
        return obj.verified_by.username if obj.verified_by else None

    def get_student_name(self, obj):
        u = obj.student_fee.student.user
        return f"{u.first_name} {u.last_name}".strip()