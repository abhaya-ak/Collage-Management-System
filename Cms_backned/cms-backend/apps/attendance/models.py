"""
Sprint 8 — Attendance domain.

    AttendanceSession  -> a teacher taking attendance for one class on one date
    AttendanceRecord   -> one row per student in that session

Rules (enforced at DB + service layers):
    * one session per class (faculty_assignment) per day  -> unique constraint
    * one record per student per session                  -> unique constraint
    * locked sessions are immutable                        -> service guard
"""

from django.db import models

from apps.core.enums import AttendanceStatus
from apps.core.models import BaseModel, SoftDeleteMixin
from apps.faculty.models import FacultyAssignment
from apps.students.models import Student


class AttendanceSession(BaseModel, SoftDeleteMixin):
    faculty_assignment = models.ForeignKey(
        FacultyAssignment, on_delete=models.PROTECT, related_name="attendance_sessions"
    )
    attendance_date = models.DateField()
    remarks = models.TextField(blank=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Attendance Session"
        verbose_name_plural = "Attendance Sessions"
        ordering = ["-attendance_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["faculty_assignment", "attendance_date"],
                condition=models.Q(is_deleted=False),
                name="unique_session_per_class_per_day",
            )
        ]

    def __str__(self):
        return f"{self.faculty_assignment} @ {self.attendance_date}"


class AttendanceRecord(BaseModel, SoftDeleteMixin):
    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="records"
    )
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="attendance_records"
    )
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)

    class Meta:
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        ordering = ["student__student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student"],
                condition=models.Q(is_deleted=False),
                name="unique_record_per_student_per_session",
            )
        ]

    def __str__(self):
        return f"{self.student.student_id}: {self.status}"
