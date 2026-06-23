"""
Fees routes → mounted at /api/fees/ by config.urls.

Generic viewset routes (admin / super-admin oriented):
    /api/fees/fee-structures/     FeeStructure CRUD
    /api/fees/student-fees/       StudentFee CRUD + generate / discount / scholarship
    /api/fees/payments/           Payment list + pay / refund
    /api/fees/receipts/           Receipt list (read-only)

Accountant-role routes:
    GET  /api/fees/accountant/student-fees/        searchable list for cash counter
    GET  /api/fees/accountant/student-fees/<pk>/   detail + payment history
    POST /api/fees/accountant/collect/             collect a payment (+ auto receipt)
    POST /api/fees/accountant/refund/<pk>/         refund a payment
    GET  /api/fees/accountant/receipts/            receipt lookup
    GET  /api/fees/accountant/daily-report/        date-ranged daily report
    GET  /api/fees/accountant/dashboard/           financial snapshot
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.fees.views import (
    AccountantCollectView,
    AccountantDailyReportView,
    AccountantDashboardView,
    AccountantReceiptListView,
    AccountantRefundView,
    AccountantStudentFeeDetailView,
    AccountantStudentFeeListView,
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

accountant_urlpatterns = [
    # Cash-counter: search & view student fees
    path(
        "accountant/student-fees/",
        AccountantStudentFeeListView.as_view(),
        name="accountant-student-fee-list",
    ),
    path(
        "accountant/student-fees/<uuid:pk>/",
        AccountantStudentFeeDetailView.as_view(),
        name="accountant-student-fee-detail",
    ),
    # Money movement
    path(
        "accountant/collect/",
        AccountantCollectView.as_view(),
        name="accountant-collect",
    ),
    path(
        "accountant/refund/<uuid:pk>/",
        AccountantRefundView.as_view(),
        name="accountant-refund",
    ),
    # Receipts
    path(
        "accountant/receipts/",
        AccountantReceiptListView.as_view(),
        name="accountant-receipt-list",
    ),
    # Reports
    path(
        "accountant/daily-report/",
        AccountantDailyReportView.as_view(),
        name="accountant-daily-report",
    ),
    path(
        "accountant/dashboard/",
        AccountantDashboardView.as_view(),
        name="accountant-dashboard",
    ),
]

urlpatterns = router.urls + accountant_urlpatterns
