# attendance/services.py
"""
Attendance domain service layer.

AttendanceService — single mark, bulk upsert, teacher ownership checks,
                    attendance percentage & per-subject summary
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import Attendance

class AttendanceService:

    @staticmethod
    def validate_date_not_future(date) -> None:
        if date > timezone.now().date():
            raise ValueError("Attendance cannot be marked for a future date.")

    @staticmethod
    def validate_no_duplicate(student, subject, date, exclude_pk=None) -> None:
        """Raises ValueError if attendance already exists for this slot."""
        qs = Attendance.objects.filter(student=student, subject=subject, date=date)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValueError(
                f"Attendance for this student in '{subject}' on {date} "
                "has already been marked. Use the update endpoint to correct it."
            )

    @staticmethod
    def validate_teacher_owns_subject(user, subject) -> None:
        """
        Raises ValueError if the user is not the assigned teacher for the subject.
        Prevents Teacher A from marking attendance in Teacher B's class.
        """
        from students.models import Teacher
        try:
            teacher = Teacher.objects.get(user=user)
        except Teacher.DoesNotExist:
            raise ValueError("Only registered teachers can mark attendance.")

        if subject and subject.teacher_id != teacher.pk:
            raise ValueError(
                f"You are not the assigned teacher for '{subject.name}'. "
                "You can only mark attendance for your own subjects."
            )

    @staticmethod
    def validate_bulk_records(records: list) -> None:
        """Raises ValueError on empty list or duplicate students in batch."""
        if not records:
            raise ValueError("Records list cannot be empty.")
        student_ids = [r['student'].pk for r in records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError(
                "Duplicate students found in the records list. "
                "Each student must appear exactly once per batch."
            )

    @staticmethod
    @transaction.atomic
    def bulk_mark(subject, date, records: list, marked_by) -> list:
        """
        Upsert strategy — update_or_create per record.
        Safe to re-run: teacher correcting a mistake will overwrite the old record.
        Returns a list of Attendance instances.
        """
        AttendanceService.validate_date_not_future(date)
        AttendanceService.validate_bulk_records(records)

        results = []
        for row in records:
            obj, _ = Attendance.objects.update_or_create(
                student = row['student'],
                subject = subject,
                date    = date,
                defaults={
                    'status':    row['status'],
                    'marked_by': marked_by,
                },
            )
            results.append(obj)
        return results

    # ── Aggregate helpers ─────────────────────────────────────────────────────

    @staticmethod
    def compute_subject_summary(student, subject_id: int | None = None) -> list[dict]:
        """
        Returns a per-subject attendance breakdown for a student.

        Policy (Option A — confirmed):
            PRESENT + LATE both count as "present" for the percentage.
            Formula: (present_count + late_count) / total_classes × 100

        Args:
            student:    students.Student instance
            subject_id: optional int — if supplied, filters to one subject

        Returns:
            List of dicts, one per subject:
            {
                'subject_id':   int,
                'subject_code': str,
                'subject_name': str,
                'total':        int,
                'present':      int,   # PRESENT records only
                'late':         int,   # LATE records only
                'absent':       int,
                'leave':        int,
                'effective_present': int,  # present + late
                'percentage':   Decimal,   # 0.00 – 100.00, 2 dp
            }

        Uses a single GROUP BY query — no N+1.
        Zero-division guarded: returns Decimal('0.00') when total == 0.
        """
        qs = (
            Attendance.objects
            .filter(student=student)
            .select_related('subject')
        )
        if subject_id is not None:
            qs = qs.filter(subject_id=subject_id)

        # Single grouped aggregate — one query regardless of subject count
        rows = (
            qs
            .values('subject__id', 'subject__code', 'subject__name')
            .annotate(
                total   = Count('id'),
                present = Count('id', filter=Q(status=Attendance.Status.PRESENT)),
                late    = Count('id', filter=Q(status=Attendance.Status.LATE)),
                absent  = Count('id', filter=Q(status=Attendance.Status.ABSENT)),
                leave   = Count('id', filter=Q(status=Attendance.Status.LEAVE)),
            )
            .order_by('subject__code')
        )

        results = []
        for row in rows:
            effective_present = row['present'] + row['late']
            total             = row['total']
            # Guard zero-division — subject with 0 total cannot appear (COUNT > 0
            # by definition), but explicit guard kept for safety.
            percentage = (
                round(Decimal(effective_present) / Decimal(total) * 100, 2)
                if total > 0
                else Decimal('0.00')
            )
            results.append({
                'subject_id':        row['subject__id'],
                'subject_code':      row['subject__code'],
                'subject_name':      row['subject__name'],
                'total':             total,
                'present':           row['present'],
                'late':              row['late'],
                'absent':            row['absent'],
                'leave':             row['leave'],
                'effective_present': effective_present,
                'percentage':        percentage,
            })
        return results

    @staticmethod
    def compute_percentage(student, subject=None) -> Decimal:
        """
        Scalar helper — overall attendance % across all subjects (or one subject).
        Useful for a single-number dashboard badge.

        Policy: LATE counts as PRESENT (Option A).
        Zero-division returns Decimal('0.00').
        """
        qs = Attendance.objects.filter(student=student)
        if subject:
            qs = qs.filter(subject=subject)
        agg = qs.aggregate(
            total   = Count('id'),
            present = Count('id', filter=Q(
                status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]
            )),
        )
        total = agg['total'] or 0
        if total == 0:
            return Decimal('0.00')
        return round(Decimal(agg['present']) / Decimal(total) * 100, 2)