"""
Sprint 5 — Academics, Phase A: Academic Structure.

Four independent models (no FKs between them yet). They form the skeleton that
Students, Faculty, Attendance, Exams, and Fees will later hang off.

Build order: AcademicYear -> Program -> Semester -> Subject
"""

from django.db import models

from apps.core.models import BaseModel, SoftDeleteMixin


# =============================================================
# 1. AcademicYear  (e.g. 2025/26)
# =============================================================
class AcademicYear(BaseModel, SoftDeleteMixin):
    name = models.CharField(max_length=20, unique=True)  # e.g. "2025/26"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"
        ordering = ["-start_date"]
        constraints = [
            # At most one academic year may be marked current.
            models.UniqueConstraint(
                fields=["is_current"],
                condition=models.Q(is_current=True),
                name="unique_current_academic_year",
            )
        ]

    def __str__(self):
        return self.name


# =============================================================
# 2. Program  (e.g. BSc.IT, BCA, BBS)
# =============================================================
class Program(BaseModel, SoftDeleteMixin):
    code = models.CharField(max_length=20, unique=True)  # e.g. "BCA"
    name = models.CharField(max_length=150)
    duration_years = models.PositiveSmallIntegerField()
    total_semesters = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Program"
        verbose_name_plural = "Programs"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================
# 3. Semester  (generic: Semester 1 .. 8)
# =============================================================
class Semester(BaseModel, SoftDeleteMixin):
    number = models.PositiveSmallIntegerField(unique=True)  # 1..8
    name = models.CharField(max_length=50)  # e.g. "Semester 1"

    class Meta:
        verbose_name = "Semester"
        verbose_name_plural = "Semesters"
        ordering = ["number"]

    def __str__(self):
        return self.name


# =============================================================
# 4. Subject  (e.g. CSC109)
# =============================================================
class Subject(BaseModel, SoftDeleteMixin):
    code = models.CharField(max_length=20, unique=True)  # e.g. "CSC109"
    name = models.CharField(max_length=150)
    credit_hours = models.PositiveSmallIntegerField(default=0)
    theory_hours = models.PositiveSmallIntegerField(default=0)
    practical_hours = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================
# Phase B — 5. ProgramSemesterSubject  (curriculum mapping)
# =============================================================
class ProgramSemesterSubject(BaseModel, SoftDeleteMixin):
    """
    Maps a reusable Subject into a specific Program + Semester.

    A single Subject (e.g. "Mathematics") can appear in many programs/semesters
    without being duplicated.

        BSc.IT -> Semester 1 -> CSC109, CSC110, ENG101
    """

    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="curriculum"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="curriculum"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="curriculum_entries"
    )
    is_elective = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Curriculum Subject"
        verbose_name_plural = "Curriculum Subjects"
        ordering = ["program", "semester", "subject"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "semester", "subject"],
                name="unique_program_semester_subject",
            )
        ]

    def __str__(self):
        return f"{self.program.code} / Sem {self.semester.number} / {self.subject.code}"


# =============================================================
# Phase C — 6. Section  (delivery layer: A / B / C)
# =============================================================
class Section(BaseModel, SoftDeleteMixin):
    """A class section within a Program + Semester (e.g. 'A', capacity 40)."""

    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="sections"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="sections"
    )
    name = models.CharField(max_length=10)  # "A", "B", "C"
    capacity = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"
        ordering = ["program", "semester", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "semester", "name"],
                name="unique_section_per_program_semester",
            )
        ]

    def __str__(self):
        return f"{self.program.code} / Sem {self.semester.number} / {self.name}"
