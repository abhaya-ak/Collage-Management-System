# fees/views.py

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from auth_core.permissions import HasPermission, IsAdminRole

from .models import FeeStructure, StudentFee, Payment
from students.models import Student
from .serializers import (
    FeeStructureReadSerializer,
    FeeStructureWriteSerializer,
    StudentFeeReadSerializer,
    StudentFeeGenerateSerializer,
    PaymentCreateSerializer,
    PaymentVerifySerializer,
    PaymentSummarySerializer,
    PaymentAdminDetailSerializer,
)

from users.constants import PermissionCodes

# ─────────────────────────────────────────────────────────────
# 1. Fee Structure
# ─────────────────────────────────────────────────────────────

class FeeStructureViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/fees/structures/           list    (student / admin / teacher)
    GET    /api/v1/fees/structures/{id}/      detail  (student / admin / teacher)
    POST   /api/v1/fees/structures/           create  (admin only)
    PUT    /api/v1/fees/structures/{id}/      update  (admin only)
    PATCH  /api/v1/fees/structures/{id}/      partial (admin only)
    DELETE /api/v1/fees/structures/{id}/      destroy (admin only)
    """
    queryset           = FeeStructure.objects.all()
    permission_classes = [HasPermission]

    @property
    def required_permission(self):
        # Students (FEES_VIEW_OWN) can read fee structures;
        # write actions are further guarded by IsAdminRole() below.
        if self.action in ('list', 'retrieve'):
            return PermissionCodes.FEES_VIEW_OWN
        return PermissionCodes.FEES_MANAGE

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return FeeStructureReadSerializer
        return FeeStructureWriteSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [HasPermission()]
        return [IsAdminRole()]


# ─────────────────────────────────────────────────────────────
# 2. Student Fee / Bills
# ─────────────────────────────────────────────────────────────

class StudentFeeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET   /api/v1/fees/bills/               list    (own bills — student | all — admin)
    GET   /api/v1/fees/bills/{id}/          detail
    POST  /api/v1/fees/bills/generate/      generate bill for a student  (admin only)

    ?search=<term>       — student name, roll number
    ?ordering=<field>    — due_date, status, created_at
    """
    serializer_class    = StudentFeeReadSerializer
    permission_classes  = [HasPermission]
    required_permission = PermissionCodes.FEES_VIEW_OWN
    filter_backends     = [SearchFilter, OrderingFilter]
    search_fields       = ['student__roll_no', 'student__user__first_name',
                           'student__user__last_name', 'status']
    ordering_fields     = ['due_date', 'status', 'created_at', 'total_amount']
    ordering            = ['-created_at']

    def get_queryset(self):
        from auth_core.services.rbac_service import RBACService
        user = self.request.user
        qs   = StudentFee.objects.select_related(
            'student', 'student__user', 'fee_structure'
        )
        if RBACService.has_permission(user, 'role:admin') or user.is_superuser:
            return qs.all()
        return qs.filter(student__user=user)

    @action(
        detail=False,
        methods=['post'],
        url_path='generate',
        permission_classes=[IsAdminRole],
    )
    def generate(self, request):
        """POST /api/v1/fees/bills/generate/"""
        serializer = StudentFeeGenerateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        bill = serializer.save()
        return Response(
            StudentFeeReadSerializer(bill, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────
# 3. Payments
# ─────────────────────────────────────────────────────────────

class PaymentViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/fees/payments/               list
    GET    /api/v1/fees/payments/{id}/          detail
    POST   /api/v1/fees/payments/               submit payment   (student)
    PUT    /api/v1/fees/payments/{id}/          update           (student)
    PATCH  /api/v1/fees/payments/{id}/          partial update   (student)
    DELETE /api/v1/fees/payments/{id}/          soft-cancel      (student — pending only)
    POST   /api/v1/fees/payments/{id}/verify/   verify payment   (admin only)

    ?search=<term>       — student name, roll, payment method
    ?ordering=<field>    — paid_at, amount, verification_status
    """
    permission_classes  = [HasPermission]
    required_permission = PermissionCodes.FEES_SUBMIT_PAYMENT
    filter_backends     = [SearchFilter, OrderingFilter]
    search_fields       = ['student_fee__student__roll_no',
                           'student_fee__student__user__first_name',
                           'student_fee__student__user__last_name',
                           'payment_method', 'verification_status', 'reference']
    ordering_fields     = ['paid_at', 'amount', 'verification_status']
    ordering            = ['-paid_at']

    def get_serializer_class(self):
        if self.action == 'verify':
            return PaymentVerifySerializer
        if self.action in ('create', 'update', 'partial_update'):
            return PaymentCreateSerializer
        return PaymentSummarySerializer

    def get_queryset(self):
        from auth_core.services.rbac_service import RBACService
        user = self.request.user
        qs   = Payment.objects.filter(is_deleted=False).select_related(
            'student_fee',
            'student_fee__student',
            'student_fee__student__user',
            'verified_by',
        )
        if RBACService.has_permission(user, 'role:admin') or user.is_superuser:
            return qs.all()
        return qs.filter(student_fee__student__user=user)

    def perform_destroy(self, instance):
        """
        Soft-delete: marks the payment as deleted instead of removing the row.
        Blocks deletion of already-verified payments to preserve the financial
        audit trail — verified records can only be reversed by admin via /verify/.
        """
        if instance.verification_status == Payment.VerificationStatus.VERIFIED:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                'Verified payments cannot be deleted. Contact an administrator to reverse this payment.'
            )
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at'])

    def perform_create(self, serializer):
        # Only registered students can submit payments
        try:
            Student.objects.get(user=self.request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Only registered students can submit payments.")
        serializer.save()

    @action(
        detail=True,
        methods=['post'],
        url_path='verify',
        permission_classes=[IsAdminRole],
    )
    def verify(self, request, pk=None):
        """POST /api/v1/fees/payments/{id}/verify/"""
        from fees.services import PaymentService
        payment = self.get_object()

        serializer = PaymentVerifySerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        try:
            updated = PaymentService.verify_payment(
                payment     = payment,
                new_status  = serializer.validated_data['verification_status'],
                admin_note  = serializer.validated_data.get('admin_note', ''),
                verified_by = request.user,
                request     = request,
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PaymentAdminDetailSerializer(updated, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )