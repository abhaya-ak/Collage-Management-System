from django.urls import path
from .views import PayFeeAPIView, StudentFeeHistoryAPIView

urlpatterns = [
    # POST: Record a new payment
    path('pay/', PayFeeAPIView.as_view(), name='pay-fees'),
    path('student/<int:id>/', StudentFeeHistoryAPIView.as_view(), name='student-fee-history'),
]