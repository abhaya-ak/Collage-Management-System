# attendance/services.py
"""
Attendance domain service layer.

AttendanceService — single mark, bulk upsert, teacher ownership checks
"""
from django.db import transaction
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