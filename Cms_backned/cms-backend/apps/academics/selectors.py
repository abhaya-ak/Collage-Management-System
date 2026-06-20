"""
Selectors — optimized read queries for academics.
Keeps query optimization (select_related) out of views.
"""

from apps.academics.models import (
    AcademicYear,
    Program,
    ProgramSemesterSubject,
    Section,
    Semester,
    Subject,
)


def academic_year_list():
    return AcademicYear.objects.all()


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
