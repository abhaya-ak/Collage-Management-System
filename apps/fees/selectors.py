"""Selectors — optimized read queries for the fees domain."""

from django.db.models import Count, Prefetch, Q, Sum
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


# =============================================================
# Accountant-specific selectors
# =============================================================

def accountant_student_fee_list(search=None, status=None, program=None,
                                academic_year=None, semester=None):
    """
    Filterable list of StudentFees for the cash-collection counter.
    Supports searching by student ID or student name.
    """
    qs = StudentFee.objects.select_related(
        "student__user", "academic_year", "program", "semester", "fee_structure"
    ).prefetch_related("payments")

    if search:
        qs = qs.filter(
            Q(student__student_id__icontains=search)
            | Q(student__user__first_name__icontains=search)
            | Q(student__user__last_name__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if program:
        qs = qs.filter(program=program)
    if academic_year:
        qs = qs.filter(academic_year=academic_year)
    if semester:
        qs = qs.filter(semester=semester)

    return qs.order_by("-created_at")


def daily_collection_report(date_from=None, date_to=None):
    """
    Payments (non-refunded) in a date range for the accountant's daily report.
    Defaults to today when no range is given.
    """
    today = timezone.localdate()
    date_from = date_from or today
    date_to = date_to or today

    return (
        Payment.objects
        .filter(
            is_refunded=False,
            paid_at__date__gte=date_from,
            paid_at__date__lte=date_to,
        )
        .select_related("student_fee__student__user", "paid_by")
        .prefetch_related("receipt")
        .order_by("-paid_at")
    )


def collection_summary_by_method(date_from=None, date_to=None) -> dict:
    """
    Aggregate collection totals grouped by payment method for the given period.
    Returns a dict ready to embed in the accountant dashboard.
    """
    today = timezone.localdate()
    date_from = date_from or today
    date_to = date_to or today

    rows = (
        Payment.objects
        .filter(
            is_refunded=False,
            paid_at__date__gte=date_from,
            paid_at__date__lte=date_to,
        )
        .values("payment_method")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("payment_method")
    )
    return {
        row["payment_method"]: {
            "total": row["total"] or 0,
            "count": row["count"],
        }
        for row in rows
    }
