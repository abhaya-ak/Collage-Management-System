"""
Fees API — thin viewsets. Money mutations route through fees.services.

    /api/fees/structures/                 FeeStructure CRUD
    /api/fees/                            StudentFee list/detail
    POST /api/fees/generate/              generate_student_fee
    POST /api/fees/{id}/apply-discount/   apply_discount
    POST /api/fees/{id}/apply-scholarship/ apply_scholarship
    GET  /api/fees/dashboard/             finance stats
    /api/fees/payments/                   payment history
    POST /api/fees/payments/pay/          pay_fee
"""

from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed

from apps.fees import selectors, serializers, services
from apps.fees.models import Receipt
from apps.fees.permissions import (
    FEE_STRUCTURE_PERMISSIONS,
    PAYMENT_PERMISSIONS,
    RECEIPT_PERMISSIONS,
    STUDENT_FEE_PERMISSIONS,
)
from apps.students.models import Student
from shared.responses import success_response
from shared.viewsets import BaseRBACViewSet


def _is_finance(user):
    return user.is_superuser or user.has_permission("view_payment")


class FeeStructureViewSet(BaseRBACViewSet):
    permission_map = FEE_STRUCTURE_PERMISSIONS
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["academic_year", "program", "semester", "is_active"]
    search_fields = ["name"]

    def get_queryset(self):
        return selectors.fee_structure_list()

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.FeeStructureCreateSerializer
        if self.action in ("update", "partial_update"):
            return serializers.FeeStructureUpdateSerializer
        return serializers.FeeStructureSerializer

    def create(self, request, *args, **kwargs):
        ser = serializers.FeeStructureCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        structure = services.create_fee_structure(actor=request.user, **ser.validated_data)
        return success_response(
            serializers.FeeStructureSerializer(structure).data,
            "Fee structure created.", 201,
        )

    def update(self, request, *args, **kwargs):
        structure = self.get_object()
        ser = serializers.FeeStructureUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        structure = services.update_fee_structure(structure, actor=request.user, **ser.validated_data)
        return success_response(
            serializers.FeeStructureSerializer(structure).data, "Fee structure updated."
        )


class StudentFeeViewSet(BaseRBACViewSet):
    permission_map = STUDENT_FEE_PERMISSIONS
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["student", "status", "academic_year", "program", "semester"]

    def get_queryset(self):
        if self.action == "retrieve":
            return selectors.student_fee_detail()
        return selectors.student_fee_list()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.StudentFeeDetailSerializer
        return serializers.StudentFeeSerializer

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="Use POST /api/fees/generate/ instead.")

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        ser = serializers.GenerateStudentFeeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        fee = services.generate_student_fee(actor=request.user, **ser.validated_data)
        return success_response(serializers.StudentFeeSerializer(fee).data,
                                "Student fee generated.", 201)

    @action(detail=True, methods=["post"], url_path="apply-discount")
    def apply_discount(self, request, pk=None):
        fee = self.get_object()
        ser = serializers.AmountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        fee = services.apply_discount(fee, ser.validated_data["amount"], actor=request.user)
        return success_response(serializers.StudentFeeSerializer(fee).data, "Discount applied.")

    @action(detail=True, methods=["post"], url_path="apply-scholarship")
    def apply_scholarship(self, request, pk=None):
        fee = self.get_object()
        ser = serializers.AmountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        fee = services.apply_scholarship(fee, ser.validated_data["amount"], actor=request.user)
        return success_response(serializers.StudentFeeSerializer(fee).data, "Scholarship applied.")

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        return success_response(selectors.fee_dashboard_stats(), "Fee dashboard.")


class PaymentViewSet(BaseRBACViewSet):
    serializer_class = serializers.PaymentSerializer
    permission_map = PAYMENT_PERMISSIONS
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["student_fee", "payment_method"]

    def get_queryset(self):
        return selectors.payment_history()

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="Use POST /api/fees/payments/pay/ instead.")

    @action(detail=False, methods=["post"], url_path="pay")
    def pay(self, request):
        ser = serializers.PayFeeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment = services.pay_fee(actor=request.user, **ser.validated_data)
        return success_response(serializers.PaymentSerializer(payment).data,
                                "Payment recorded.", 201)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        payment = self.get_object()
        ser = serializers.RefundSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment = services.refund_payment(payment, reason=ser.validated_data["reason"],
                                           actor=request.user)
        return success_response(serializers.PaymentSerializer(payment).data,
                                "Payment refunded.")


class ReceiptViewSet(BaseRBACViewSet):
    serializer_class = serializers.ReceiptSerializer
    permission_map = RECEIPT_PERMISSIONS
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["payment"]

    def get_queryset(self):
        qs = Receipt.objects.select_related(
            "payment__student_fee__student"
        ).order_by("-generated_at")
        user = self.request.user
        if _is_finance(user):
            return qs
        # Students see only their own receipts.
        student = Student.objects.filter(user=user).first()
        if student:
            return qs.filter(payment__student_fee__student=student)
        return qs.none()
