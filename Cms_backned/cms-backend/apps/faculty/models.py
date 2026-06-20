"""
Sprint 7 — Faculty domain.

    Faculty             -> teacher identity (linked to a CustomUser)
    FacultyAssignment   -> who teaches which subject, to which section,
                           in which semester/program/academic year

Rule: NO direct Faculty -> Student link. Students reach faculty indirectly:
    Faculty -> FacultyAssignment -> Subject/Section/Semester/Program
    Student -> StudentEnrollment -> same Section/Semester/Program
"""

from django.conf import settings
from django.db import models

from apps.academics.models import AcademicYear, Program, Section, Semester, Subject
from apps.core.enums import FacultyStatus
from apps.core.models import BaseModel, SoftDeleteMixin


# =============================================================
# Faculty — identity
# =============================================================
class Faculty(BaseModel, SoftDeleteMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="faculty",
    )
    employee_id = models.CharField(max_length=30, unique=True)
    designation = models.CharField(max_length=100, blank=True)  # e.g. Lecturer, Professor
    join_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=FacultyStatus.choices, default=FacultyStatus.ACTIVE
    )

    class Meta:
        verbose_name = "Faculty"
        verbose_name_plural = "Faculty"
        ordering = ["employee_id"]

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"

    @property
    def full_name(self):
        return self.user.full_name


# =============================================================
# FacultyAssignment — teaching map
# =============================================================
class FacultyAssignment(BaseModel, SoftDeleteMixin):
    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE, related_name="assignments"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="faculty_assignments"
    )
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="faculty_assignments"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="faculty_assignments"
    )
    section = models.ForeignKey(
        Section, on_delete=models.PROTECT, related_name="faculty_assignments"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="faculty_assignments"
    )

    class Meta:
        verbose_name = "Faculty Assignment"
        verbose_name_plural = "Faculty Assignments"
        ordering = ["-created_at"]
        constraints = [
            # One teacher per subject, per section, per semester/program/year.
            models.UniqueConstraint(
                fields=["academic_year", "program", "semester", "section", "subject"],
                condition=models.Q(is_deleted=False),
                name="unique_subject_assignment_per_section",
            )
        ]

    def __str__(self):
        return (
            f"{self.faculty.employee_id}: {self.subject.code} -> "
            f"{self.program.code} Sem{self.semester.number} {self.section.name}"
        )
