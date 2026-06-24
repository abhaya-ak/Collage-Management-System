"""
Selectors — optimized read queries for academics.
Keeps query optimization (select_related) out of views.
"""

from django.db.models import Count, Q

from apps.academics.models import (
    AcademicYear,
    Program,
    ProgramSemesterSubject,
    Section,
    Semester,
    Subject,
)
from apps.core.exceptions import InvalidOperation


def academic_year_list():
    return AcademicYear.objects.all()


def get_current_academic_year() -> AcademicYear:
    """
    Return the single AcademicYear marked is_current=True.
    Raises InvalidOperation if none has been configured — forces admin to set
    a current year before admissions can proceed.
    """
    year = AcademicYear.objects.filter(is_current=True).first()
    if year is None:
        raise InvalidOperation(
            "No current academic year is configured. "
            "Please mark an academic year as current before admitting students."
        )
    return year


def program_list():
    return Program.objects.all()


def semester_list():
    return Semester.objects.all()


def subject_list():
    return Subject.objects.all()


def section_list():
    return Section.objects.select_related("program", "semester")


def curriculum_list():
    return ProgramSemesterSubject.objects.select_related(
        "program", "semester", "subject"
    )


def get_section_capacity_stats(*, program_id=None, semester_id=None):
    """
    Phase 4 — Capacity Dashboard selector.

    Returns all non-deleted sections annotated with:
        active_count — current ACTIVE (non-deleted) enrollment count
        fill_pct     — float 0.0-100.0; 0.0 when capacity==0 (unlimited)

    Optional filters:
        program_id  — UUID
        semester_id — UUID

    Used by:
        GET /api/academics/sections/capacity/
    """
    from django.db.models import Case, ExpressionWrapper, F, FloatField, When

    active_q = Q(enrollments__status="ACTIVE", enrollments__is_deleted=False)

    qs = (
        Section.objects
        .select_related("program", "semester")
        .annotate(active_count=Count("enrollments", filter=active_q))
        .annotate(
            fill_pct=Case(
                When(capacity=0, then=0.0),          # unlimited → show 0%
                default=ExpressionWrapper(
                    F("active_count") * 100.0 / F("capacity"),
                    output_field=FloatField(),
                ),
            )
        )
        .order_by("program__code", "semester__number", "name")
    )

    if program_id:
        qs = qs.filter(program_id=program_id)
    if semester_id:
        qs = qs.filter(semester_id=semester_id)

    return qs


