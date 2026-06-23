"""
Fees API — thin viewsets. Money mutations route through fees.services.

    /api/fees/structures/                  FeeStructure CRUD
    /api/fees/student-fees/                StudentFee list/detail
    POST /api/fees/student-fees/generate/  generate_student_fee
    POST /api/fees/student-fees/{id}/apply-discount/
    POST /api/fees/student-fees/{id}/apply-scholarship/
    GET  /api/fees/student-fees/dashboard/ finance stats
    /api/fees/payments/                    payment history
    POST /api/fees/payments/pay/           pay_fee

Accountant-role endpoints (all under /api/fees/accountant/):
    GET  /api/fees/accountant/student-fees/       searchable fee list (cash counter)
    GET  /api/fees/accountant/student-fees/{id}/  detail with payment history
    POST /api/fees/accountant/collect/            collect a payment (pay_fee)
    POST /api/fees/accountant/refund/{id}/        refund a payment
    GET  /api/fees/accountant/receipts/           receipts for a student or fee
    GET  /api/fees/accountant/daily-report/       date-ranged collection report
    GET  /api/fees/accountant/dashboard/          financial snapshot
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import HasPermission
from apps.fees import selectors, serializers, services
from apps.fees.models import Payment, Receipt
from apps.fees.permissions import (
    FEE_STRUCTURE_PERMISSIONS,
    PAYMENT_PERMISSIONS,
    RECEIPT_PERMISSIONS,
    STUDENT_FEE_PERMISSIONS,
)
from apps.students.models import Student
from shared.responses import error_response, success_response
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


# =============================================================
# Accountant role — dedicated views
# =============================================================

class AccountantStudentFeeListView(APIView):
    """
    GET /api/fees/accountant/student-fees/

    Searchable, filterable list of student fees for the cash-collection counter.

    Query params:
        search          — student ID or name fragment
        status          — PENDING | PARTIAL | OVERDUE | PAID | CANCELLED
        program         — program UUID
        academic_year   — academic year UUID
        semester        — semester UUID
    """

    permission_classes = [IsAuthenticated, HasPermission("view_student_fee")]

    def get(self, request):
        qs = selectors.accountant_student_fee_list(
            search=request.query_params.get("search"),
            status=request.query_params.get("status"),
            program=request.query_params.get("program"),
            academic_year=request.query_params.get("academic_year"),
            semester=request.query_params.get("semester"),
        )
        ser = serializers.AccountantStudentFeeSerializer(qs, many=True)
        return success_response(ser.data, f"{qs.count()} record(s) found.")


class AccountantStudentFeeDetailView(APIView):
    """
    GET /api/fees/accountant/student-fees/<pk>/

    Full fee record including all payment + receipt history for a student.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_student_fee")]

    def get(self, request, pk):
        try:
            fee = selectors.student_fee_detail().get(pk=pk)
        except Exception:
            return error_response("Fee record not found.", status.HTTP_404_NOT_FOUND)
        ser = serializers.StudentFeeDetailSerializer(fee)
        return success_response(ser.data, "Fee detail fetched.")


class AccountantCollectView(APIView):
    """
    POST /api/fees/accountant/collect/

    Record a fee payment (cash / transfer / eSewa / Khalti / …).
    Auto-generates a receipt (RCT-YYYY-XXXX).

    Body:
        student_fee      (UUID)
        amount           (decimal)
        payment_method   (CASH | BANK_TRANSFER | ESEWA | KHALTI | CARD | CHEQUE)
        reference_number (optional string)
        remarks          (optional string)
    """

    permission_classes = [IsAuthenticated, HasPermission("pay_fee")]

    def post(self, request):
        ser = serializers.PayFeeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment = services.pay_fee(actor=request.user, **ser.validated_data)
        return success_response(
            serializers.PaymentSerializer(payment).data,
            "Payment recorded and receipt generated.",
            status.HTTP_201_CREATED,
        )


class AccountantRefundView(APIView):
    """
    POST /api/fees/accountant/refund/<payment_pk>/

    Refund a previously recorded payment.  The fee's paid/due amounts are
    recomputed atomically; the original payment + receipt are retained for audit.

    Body:
        reason  (optional string)
    """

    permission_classes = [IsAuthenticated, HasPermission("refund_payment")]

    def post(self, request, pk):
        try:
            payment = Payment.objects.get(pk=pk)
        except Payment.DoesNotExist:
            return error_response("Payment not found.", status.HTTP_404_NOT_FOUND)

        ser = serializers.RefundSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment = services.refund_payment(
            payment, reason=ser.validated_data["reason"], actor=request.user
        )
        return success_response(
            serializers.PaymentSerializer(payment).data,
            "Payment refunded successfully.",
        )


class AccountantReceiptListView(APIView):
    """
    GET /api/fees/accountant/receipts/

    Receipts for a specific student or student-fee record.

    Query params:
        student_fee  — UUID of the StudentFee (optional)
        student      — UUID of the Student    (optional)
    """

    permission_classes = [IsAuthenticated, HasPermission("view_receipt")]

    def get(self, request):
        qs = Receipt.objects.select_related(
            "payment__student_fee__student__user", "payment__paid_by"
        ).order_by("-generated_at")

        student_fee_id = request.query_params.get("student_fee")
        student_id = request.query_params.get("student")

        if student_fee_id:
            qs = qs.filter(payment__student_fee_id=student_fee_id)
        if student_id:
            qs = qs.filter(payment__student_fee__student_id=student_id)

        ser = serializers.ReceiptSerializer(qs, many=True)
        return success_response(ser.data, f"{qs.count()} receipt(s) found.")


class AccountantDailyReportView(APIView):
    """
    GET /api/fees/accountant/daily-report/

    Date-ranged collection report — every non-refunded payment in the window.
    Defaults to today's collections when no dates are supplied.

    Query params:
        date_from  (YYYY-MM-DD, optional — defaults to today)
        date_to    (YYYY-MM-DD, optional — defaults to today)
    """

    permission_classes = [IsAuthenticated, HasPermission("view_payment")]

    def get(self, request):
        qser = serializers.CollectionReportQuerySerializer(
            data=request.query_params
        )
        qser.is_valid(raise_exception=True)

        date_from = qser.validated_data.get("date_from")
        date_to = qser.validated_data.get("date_to")

        payments = selectors.daily_collection_report(
            date_from=date_from, date_to=date_to
        )
        by_method = selectors.collection_summary_by_method(
            date_from=date_from, date_to=date_to
        )

        data = {
            "period": {
                "date_from": str(date_from) if date_from else "today",
                "date_to": str(date_to) if date_to else "today",
            },
            "total_collected": sum(
                p.amount for p in payments if not p.is_refunded
            ),
            "total_transactions": payments.count(),
            "breakdown_by_method": by_method,
            "transactions": serializers.DailyCollectionEntrySerializer(
                payments, many=True
            ).data,
        }
        return success_response(data, "Daily collection report.")


class AccountantDashboardView(APIView):
    """
    GET /api/fees/accountant/dashboard/

    High-level financial snapshot: total charged, collected, outstanding,
    count by status, and today's collection summary.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_student_fee")]

    def get(self, request):
        stats = selectors.fee_dashboard_stats()
        today_by_method = selectors.collection_summary_by_method()  # defaults to today

        data = {
            **stats,
            "today_collection": today_by_method,
            "pending_count": selectors.pending_fees().count(),
            "overdue_count": selectors.overdue_fees().count(),
        }
        return success_response(data, "Accountant dashboard.")
