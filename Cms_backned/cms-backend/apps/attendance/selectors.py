"""Selectors — optimized read queries for attendance."""

from django.db.models import Prefetch

from apps.attendance.models import AttendanceRecord, AttendanceSession

_ASSIGNMENT_RELATED = (
    "faculty_assignment__faculty__user",
    "faculty_assignment__academic_year",
    "faculty_assignment__program",
    "faculty_assignment__semester",
    "faculty_assignment__section",
    "faculty_assignment__subject",
)


def session_list():
    return AttendanceSession.objects.select_related(*_ASSIGNMENT_RELATED)


def session_detail_qs():
    return AttendanceSession.objects.select_related(*_ASSIGNMENT_RELATED).prefetch_related(
        Prefetch(
            "records",
            queryset=AttendanceRecord.objects.select_related("student"),
        )
    )
