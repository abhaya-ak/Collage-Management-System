"""Fees routes -> mounted at /api/fees/ by config.urls."""

from rest_framework.routers import DefaultRouter

from apps.fees.views import (
    FeeStructureViewSet,
    PaymentViewSet,
    ReceiptViewSet,
    StudentFeeViewSet,
)

app_name = "fees"

router = DefaultRouter()
router.register("fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register("student-fees", StudentFeeViewSet, basename="student-fee")
router.register("payments", PaymentViewSet, basename="payment")
router.register("receipts", ReceiptViewSet, basename="receipt")

urlpatterns = router.urls
