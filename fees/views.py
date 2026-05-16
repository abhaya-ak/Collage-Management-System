from rest_framework import generics, permissions
from .models import Payment
#from .serializers import FeePaymentWriteSerializer, FeePaymentReadSerializer

class PayFeeAPIView(generics.CreateAPIView):
    """
    POST /api/v1/fees/pay/
    """
    serializer_class = 'FeePaymentWriteSerializer'
    
    # Only staff/admins should be able to manually record arbitrary fee payments.
    # (If integrating Stripe/PayPal for students, this logic changes to verify webhooks).
    permission_classes = [permissions.IsAdminUser] 

    def perform_create(self, serializer):
        # We can force the status to "COMPLETED" if an admin is manually recording a cash payment.
        serializer.save(status='COMPLETED')

class StudentFeeHistoryAPIView(generics.ListAPIView):
    """
    GET /api/v1/fees/student/{id}/
    """
    serializer_class = 'FeePaymentReadSerializer'
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        student_id = self.kwargs.get('id')
        
        # Ensure a student can only view their own fee history, unless they are an admin
        if not self.request.user.is_staff:
            # Check if the logged-in user matches the requested student ID
            if not getattr(self.request.user, 'student', None) or self.request.user.student.id != student_id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You can only view your own fee history.")
        
        # Return payments sorted by newest first
        return Payment.objects.filter(student_id=student_id).order_by('-payment_date')