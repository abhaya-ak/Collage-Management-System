# dashboard/services.py
"""
Dashboard domain service layer.

DashboardService.get_overview() — aggregates key metrics from all domain apps
into a single dict using ONE query per domain (no N+1, no raw SQL).

All divisions are guarded against zero-division.
All monetary values use Decimal aggregation.
"""
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone


class DashboardService:

    @staticmethod
    def get_overview() -> dict:
        """
        Returns a metrics dict for the admin dashboard overview.

        Domains covered:
          - students   : total + active count
          - attendance : today's marked records + overall avg percentage
          - fees       : billed vs collected vs pending bills
          - feedback   : breakdown by status
          - notices    : active notice count

        Each domain is one aggregate query. Total: 5 DB queries.
        """
        return {
            'students':   DashboardService._student_stats(),
            'attendance': DashboardService._attendance_stats(),
            'fees':       DashboardService._fee_stats(),
            'feedback':   DashboardService._feedback_stats(),
            'notices':    DashboardService._notice_stats(),
        }

    # ── Domain helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _student_stats() -> dict:
        from students.models import Student
        agg = Student.objects.aggregate(total=Count('id'))
        return {
            'total': agg['total'] or 0,
        }

    @staticmethod
    def _attendance_stats() -> dict:
        from attendance.models import Attendance
        today = timezone.now().date()

        agg = Attendance.objects.aggregate(
            today_marked = Count('id', filter=Q(date=today)),
            total        = Count('id'),
            # LATE counts as present (Option A — confirmed policy)
            present      = Count('id', filter=Q(
                status__in=[
                    Attendance.Status.PRESENT,
                    Attendance.Status.LATE,
                ]
            )),
        )
        total   = agg['total'] or 0
        present = agg['present'] or 0
        # Guard zero-division
        avg_pct = (
            round(Decimal(present) / Decimal(total) * 100, 2)
            if total > 0
            else Decimal('0.00')
        )
        return {
            'today_marked':   agg['today_marked'] or 0,
            'overall_avg_pct': str(avg_pct),
        }

    @staticmethod
    def _fee_stats() -> dict:
        from fees.models import StudentFee
        agg = StudentFee.objects.aggregate(
            total_billed    = Sum('total_amount'),
            total_collected = Sum('amount_paid'),
            pending_bills   = Count('id', filter=Q(status='pending')),
            partial_bills   = Count('id', filter=Q(status='partial')),
            paid_bills      = Count('id', filter=Q(status='paid')),
        )
        billed    = agg['total_billed']    or Decimal('0.00')
        collected = agg['total_collected'] or Decimal('0.00')
        return {
            'total_billed':    str(billed),
            'total_collected': str(collected),
            'outstanding':     str(billed - collected),
            'pending_bills':   agg['pending_bills']  or 0,
            'partial_bills':   agg['partial_bills']  or 0,
            'paid_bills':      agg['paid_bills']     or 0,
        }

    @staticmethod
    def _feedback_stats() -> dict:
        from feedback.models import Feedback
        agg = Feedback.objects.aggregate(
            pending  = Count('id', filter=Q(status='pending')),
            reviewed = Count('id', filter=Q(status='reviewed')),
            resolved = Count('id', filter=Q(status='resolved')),
            closed   = Count('id', filter=Q(status='closed')),
            total    = Count('id'),
        )
        return {
            'total':    agg['total']    or 0,
            'pending':  agg['pending']  or 0,
            'reviewed': agg['reviewed'] or 0,
            'resolved': agg['resolved'] or 0,
            'closed':   agg['closed']   or 0,
        }

    @staticmethod
    def _notice_stats() -> dict:
        from notices.models import Notice
        agg = Notice.objects.aggregate(
            active   = Count('id', filter=Q(is_active=True)),
            inactive = Count('id', filter=Q(is_active=False)),
            urgent   = Count('id', filter=Q(is_active=True, priority='urgent')),
        )
        return {
            'active':   agg['active']   or 0,
            'inactive': agg['inactive'] or 0,
            'urgent':   agg['urgent']   or 0,
        }
