"""
Selectors — optimized read queries for the students domain.
"""

from django.db.models import Prefetch

from apps.students.models import Student, StudentEnrollment

_ENROLLMENT_RELATED = ("academic_year", "program", "semester", "section")


def _enrollment_qs():
    return StudentEnrollment.objects.select_related(*_ENROLLMENT_RELATED)


def student_list():
    """List queryset: user joined, enrollments prefetched (for active-enrollment)."""
    return Student.objects.select_related("user").prefetch_related(
        Prefetch("enrollments", queryset=_enrollment_qs())
    )


def student_detail_qs():
    """Detail queryset: adds documents prefetch for the profile view."""
    return Student.objects.select_related("user").prefetch_related(
        Prefetch("enrollments", queryset=_enrollment_qs()),
        "documents",
    )


def get_student_profile(pk):
    """Single student with everything needed for the profile page."""
    return student_detail_qs().filter(pk=pk).first()


def get_student_enrollment_history(student):
    """All enrollments for a student, newest first, fully joined."""
    return _enrollment_qs().filter(student=student)


def get_active_enrollment(student):
    """The student's single ACTIVE enrollment, or None."""
    return _enrollment_qs().filter(student=student, status="ACTIVE").first()
