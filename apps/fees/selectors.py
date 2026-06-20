"""Selectors — optimized read queries for the fees domain."""

from django.db.models import Count, Prefetch, Sum
from django.utils import timezone

from apps.core.enums import FeeStatus
from apps.fees.models import FeeStructure, Payment, StudentFee

_OPEN_STATUSES = [FeeStatus.PENDING, FeeStatus.PARTIAL, FeeStatus.OVERDUE]


def fee_structure_list():
    return FeeStructure.objects.select_related(
        "academic_year", "program", "semester"
    ).prefetch_related("components")


def student_fee_list():
    return StudentFee.objects.select_related(
        "student", "academic_year", "program", "semester", "fee_structure"
    )


def student_fee_detail():
    return student_fee_list().prefetch_related(
        Prefetch(
            "payments",
            queryset=Payment.objects.select_related("paid_by").prefetch_related("receipt"),
        )
    )


def payment_history(student_fee=None, student=None):
    qs = Payment.objects.select_related(
        "student_fee__student", "paid_by"
    ).prefetch_related("receipt").order_by("-paid_at")
    if student_fee is not None:
        qs = qs.filter(student_fee=student_fee)
    if student is not None:
        qs = qs.filter(student_fee__student=student)
    return qs


def pending_fees():
    return student_fee_list().filter(status__in=_OPEN_STATUSES)


def overdue_fees():
    today = timezone.localdate()
    return student_fee_list().filter(
        due_date__lt=today, status__in=[FeeStatus.PENDING, FeeStatus.PARTIAL, FeeStatus.OVERDUE]
    )


def fee_dashboard_stats() -> dict:
    """Aggregate finance snapshot for the dashboard."""
    agg = StudentFee.objects.aggregate(
        total_charged=Sum("total_amount"),
        total_discount=Sum("discount_amount"),
        total_scholarship=Sum("scholarship_amount"),
        total_collected=Sum("paid_amount"),
        total_outstanding=Sum("due_amount"),
    )
    by_status = {
        row["status"]: row["n"]
        for row in StudentFee.objects.values("status").annotate(n=Count("id"))
    }
    return {
        "total_charged": agg["total_charged"] or 0,
        "total_discount": agg["total_discount"] or 0,
        "total_scholarship": agg["total_scholarship"] or 0,
        "total_collected": agg["total_collected"] or 0,
        "total_outstanding": agg["total_outstanding"] or 0,
        "count_by_status": by_status,
    }
