"""Selectors — optimized read queries for the faculty domain."""

from django.db.models import Prefetch

from apps.faculty.models import Faculty, FacultyAssignment

_ASSIGNMENT_RELATED = ("academic_year", "program", "semester", "section", "subject")


def _assignment_qs():
    return FacultyAssignment.objects.select_related(*_ASSIGNMENT_RELATED)


def faculty_list():
    return Faculty.objects.select_related("user")


def faculty_detail_qs():
    return Faculty.objects.select_related("user").prefetch_related(
        Prefetch("assignments", queryset=_assignment_qs())
    )


def get_faculty_profile(pk):
    return faculty_detail_qs().filter(pk=pk).first()


def get_faculty_assignments(faculty):
    return _assignment_qs().filter(faculty=faculty)
