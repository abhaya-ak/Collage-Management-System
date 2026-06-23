"""Serializers for the fees domain."""

from rest_framework import serializers

from apps.academics.models import AcademicYear, Program, Semester
from apps.core.enums import PaymentMethod
from apps.fees.models import FeeComponent, FeeStructure, Payment, Receipt, StudentFee
from apps.students.models import Student


# --- Fee structure ----------------------------------------------------------
class FeeComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeComponent
        fields = ["id", "name", "amount", "is_optional"]


class FeeStructureSerializer(serializers.ModelSerializer):
    components = FeeComponentSerializer(many=True, read_only=True)

    class Meta:
        model = FeeStructure
        fields = ["id", "academic_year", "program", "semester", "name",
                  "total_amount", "description", "is_active", "components", "created_at"]
        read_only_fields = ["id", "total_amount", "components", "created_at"]


class _ComponentInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_optional = serializers.BooleanField(required=False, default=False)


class FeeStructureCreateSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects.all())
    program = serializers.PrimaryKeyRelatedField(queryset=Program.objects.all())
    semester = serializers.PrimaryKeyRelatedField(queryset=Semester.objects.all())
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(required=False, default=True)
    components = _ComponentInputSerializer(many=True, allow_empty=False)


class FeeStructureUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    components = _ComponentInputSerializer(many=True, required=False)


# --- Student fee ------------------------------------------------------------
class StudentFeeSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="student.student_id", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    payable_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = StudentFee
        fields = ["id", "student", "student_name", "academic_year", "program",
                  "semester", "fee_structure", "total_amount", "discount_amount",
                  "scholarship_amount", "payable_amount", "paid_amount", "due_amount",
                  "status", "due_date", "created_at"]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="student_fee.student.student_id", read_only=True)
    paid_by = serializers.CharField(source="paid_by.email", read_only=True, default=None)
    receipt_number = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "student_fee", "student", "amount", "payment_method",
                  "reference_number", "remarks", "paid_by", "paid_at", "receipt_number",
                  "is_refunded", "refunded_at", "refund_reason"]
        read_only_fields = fields

    def get_receipt_number(self, obj):
        try:
            return obj.receipt.receipt_number
        except Exception:
            return None


class ReceiptSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="payment.student_fee.student.student_id", read_only=True)
    payment_method = serializers.CharField(source="payment.payment_method", read_only=True)

    class Meta:
        model = Receipt
        fields = ["id", "receipt_number", "amount", "generated_at", "pdf_path",
                  "payment", "student", "payment_method"]
        read_only_fields = fields


class RefundSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class StudentFeeDetailSerializer(StudentFeeSerializer):
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta(StudentFeeSerializer.Meta):
        fields = StudentFeeSerializer.Meta.fields + ["payments"]


# --- write payloads ---------------------------------------------------------
class GenerateStudentFeeSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    fee_structure = serializers.PrimaryKeyRelatedField(queryset=FeeStructure.objects.all())
    due_date = serializers.DateField(required=False, allow_null=True)


class AmountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class PayFeeSerializer(serializers.Serializer):
    student_fee = serializers.PrimaryKeyRelatedField(queryset=StudentFee.objects.all())
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference_number = serializers.CharField(required=False, allow_blank=True, default="")
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Accountant-specific serializers
# ---------------------------------------------------------------------------

class AccountantStudentFeeSerializer(serializers.ModelSerializer):
    """Compact read-only fee record used at the accountant's cash counter."""

    student_id = serializers.CharField(source="student.student_id", read_only=True)
    student_name = serializers.SerializerMethodField()
    program_name = serializers.CharField(source="program.name", read_only=True)
    semester_number = serializers.IntegerField(source="semester.number", read_only=True)
    academic_year_label = serializers.CharField(source="academic_year.label", read_only=True)
    payable_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = StudentFee
        fields = [
            "id", "student_id", "student_name",
            "program_name", "semester_number", "academic_year_label",
            "total_amount", "discount_amount", "scholarship_amount",
            "payable_amount", "paid_amount", "due_amount",
            "status", "due_date",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.email


class DailyCollectionEntrySerializer(serializers.ModelSerializer):
    """Single payment line for the daily collection report."""

    student_id = serializers.CharField(
        source="student_fee.student.student_id", read_only=True
    )
    student_name = serializers.SerializerMethodField()
    receipt_number = serializers.SerializerMethodField()
    collected_by = serializers.CharField(source="paid_by.email", read_only=True, default=None)

    class Meta:
        model = Payment
        fields = [
            "id", "student_id", "student_name",
            "amount", "payment_method", "reference_number",
            "remarks", "collected_by", "paid_at", "receipt_number",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        user = obj.student_fee.student.user
        return user.get_full_name() or user.email

    def get_receipt_number(self, obj):
        try:
            return obj.receipt.receipt_number
        except Exception:
            return None


class CollectionReportQuerySerializer(serializers.Serializer):
    """Query-param validator for date-ranged accountant reports."""

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, data):
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_to": "date_to must be on or after date_from."}
            )
        return data
