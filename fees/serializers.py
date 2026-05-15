from decimal import Decimal
from rest_framework import serializers
from .models import FeeStructure, Payment, StudentFee

class FeeStructureSerializer(serializers.ModelSerializer):
    """
    Used by admins to create and update fee plans.
    Exposed to students as a nested read inside StudentFeeSerializer.
    """

    # Computed field from the model property — always read-only
    total = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "course",
            "year",
            "semester",
            "tuition_fee",
            "exam_fee",
            "library_fee",
            "miscellaneous_fee",
            "total",          # computed
            "due_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        """
        Ensure at least one fee component is greater than zero.
        A plan where everything is 0.00 is almost certainly a mistake.
        """
        fee_fields = ["tuition_fee", "exam_fee", "library_fee", "miscellaneous_fee"]
        total = sum(attrs.get(f, Decimal("0.00")) for f in fee_fields)
        if total <= Decimal("0.00"):
            raise serializers.ValidationError(
                "A fee structure must have at least one non-zero fee component."
            )
        return attrs

class PaymentSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight read-only view of a payment — used when nested inside a
    student's fee bill. Excludes admin-only fields like admin_note.
    """

    payment_method_display = serializers.CharField(
        source="get_payment_method_display",
        read_only=True,
    )
    verification_status_display = serializers.CharField(
        source="get_verification_status_display",
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "payment_method",
            "payment_method_display",
            "reference",
            "screenshot",
            "verification_status",
            "verification_status_display",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields

class StudentFeeSerializer(serializers.ModelSerializer):
    """
    Read-only bill view for a student.
    Includes the fee plan breakdown and all payment attempts.
    """

    fee_structure = FeeStructureSerializer(read_only=True)
    payments = PaymentSummarySerializer(many=True, read_only=True)

    # Computed from model property
    balance_due = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = StudentFee
        fields = [
            "id",
            "student",
            "fee_structure",
            "total_amount",
            "amount_paid",
            "balance_due",      # computed
            "status",
            "status_display",   # human label
            "due_date",
            "remarks",
            "payments",         # full payment history
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Payment — student submits a new payment
# ---------------------------------------------------------------------------


class PaymentCreateSerializer(serializers.ModelSerializer):
    """
    Used when a student submits a payment with proof.

    Enforces:
    - Amount cannot exceed the remaining balance
    - Screenshot is required for QR and bank transfers
    - Cannot pay an already-settled bill
    """

    class Meta:
        model = Payment
        fields = [
            "id",
            "student_fee",
            "amount",
            "payment_method",
            "reference",
            "screenshot",
            "paid_at",
        ]
        read_only_fields = ["id"]

    def validate_student_fee(self, student_fee):
        """Block payment submissions against an already fully paid bill."""
        if student_fee.status == StudentFee.Status.PAID:
            raise serializers.ValidationError(
                "This fee has already been fully paid. No further payments are accepted."
            )
        return student_fee

    def validate(self, attrs):
        student_fee = attrs["student_fee"]
        amount = attrs["amount"]
        payment_method = attrs.get("payment_method", Payment.Method.CASH)
        screenshot = attrs.get("screenshot")

        # Rule 1: Payment cannot exceed what's still owed
        if amount > student_fee.balance_due:
            raise serializers.ValidationError(
                {
                    "amount": (
                        f"Payment of {amount} exceeds the remaining balance of "
                        f"{student_fee.balance_due}. "
                        "Overpayment is not allowed."
                    )
                }
            )

        # Rule 2: QR and bank transfers must include a screenshot
        digital_methods = {Payment.Method.QR, Payment.Method.BANK}
        if payment_method in digital_methods and not screenshot:
            raise serializers.ValidationError(
                {
                    "screenshot": (
                        "A payment screenshot is required for QR and bank transfer payments."
                    )
                }
            )

        return attrs


# ---------------------------------------------------------------------------
# Payment — admin verifies or rejects a payment
# ---------------------------------------------------------------------------


class PaymentVerifySerializer(serializers.ModelSerializer):
    """
    Used by admin to approve or reject a pending payment.

    The view is responsible for:
    - Setting verified_by = request.user
    - Setting verified_at = now()
    - Calling student_fee.recompute_status() after verification
    """

    class Meta:
        model = Payment
        fields = [
            "id",
            "verification_status",
            "admin_note",
        ]
        read_only_fields = ["id"]

    def validate_verification_status(self, value):
        """
        Prevent re-processing an already decided payment.
        Once verified or rejected, it should not flip again without
        a deliberate admin override — that belongs in a separate endpoint.
        """
        instance = self.instance
        if instance and instance.verification_status != Payment.VerificationStatus.PENDING:
            raise serializers.ValidationError(
                f"This payment has already been '{instance.verification_status}'. "
                "Only pending payments can be verified or rejected here."
            )
        return value

    def validate(self, attrs):
        """
        If admin is rejecting, a note explaining why should be provided.
        This is not hard-blocked but warned — keeps audit trail meaningful.
        """
        status = attrs.get("verification_status")
        note = attrs.get("admin_note", "").strip()

        if status == Payment.VerificationStatus.REJECTED and not note:
            raise serializers.ValidationError(
                {
                    "admin_note": (
                        "Please provide a reason when rejecting a payment. "
                        "The student needs to know what went wrong."
                    )
                }
            )
        return attrs


# ---------------------------------------------------------------------------
# Payment — full detail view for admin (read-only)
# ---------------------------------------------------------------------------


class PaymentAdminDetailSerializer(serializers.ModelSerializer):
    """
    Full payment record for admin review screens.
    Includes all fields including who verified and when.
    """

    payment_method_display = serializers.CharField(
        source="get_payment_method_display",
        read_only=True,
    )
    verification_status_display = serializers.CharField(
        source="get_verification_status_display",
        read_only=True,
    )
    verified_by_username = serializers.CharField(
        source="verified_by.username",
        read_only=True,
        default=None,
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "student_fee",
            "amount",
            "payment_method",
            "payment_method_display",
            "reference",
            "screenshot",
            "verification_status",
            "verification_status_display",
            "verified_by",
            "verified_by_username",
            "verified_at",
            "admin_note",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields