"""
Exam & Result domain — Step 1: the grading engine foundation.

GradeScale is the configurable policy that Marks -> GPA -> CGPA -> Result ->
Transcript all depend on. Built BEFORE any exam model on purpose.

A GradeScale row maps a marks range to a letter grade and grade point, e.g.
    90.00–100.00  -> A+  (4.00)
    0.00–34.99    -> F   (0.00, not passing)
"""

from django.conf import settings
from django.db import models

from apps.academics.models import AcademicYear, Program, Section, Semester, Subject
from apps.core.enums import ExamStatus, ExamType
from apps.core.models import BaseModel, SoftDeleteMixin
from apps.students.models import Student


class GradeScale(BaseModel, SoftDeleteMixin):
    grade = models.CharField(max_length=5, unique=True)          # "A+", "A", ... "F"
    min_marks = models.DecimalField(max_digits=5, decimal_places=2)   # inclusive
    max_marks = models.DecimalField(max_digits=5, decimal_places=2)   # inclusive
    grade_point = models.DecimalField(max_digits=3, decimal_places=2)  # 0.00–4.00
    description = models.CharField(max_length=100, blank=True)
    is_passing = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Grade Scale"
        verbose_name_plural = "Grade Scales"
        ordering = ["-min_marks"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_marks__lte=models.F("max_marks")),
                name="grade_min_lte_max",
            )
        ]

    def __str__(self):
        return f"{self.grade} ({self.min_marks}-{self.max_marks}) = {self.grade_point}"


# =============================================================
# Exam Structure (Sprint 9.1) — models only
# =============================================================
class Exam(BaseModel, SoftDeleteMixin):
    name = models.CharField(max_length=150)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="exams"
    )
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="exams"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="exams"
    )
    exam_type = models.CharField(max_length=20, choices=ExamType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=ExamStatus.choices, default=ExamStatus.DRAFT
    )

    class Meta:
        verbose_name = "Exam"
        verbose_name_plural = "Exams"
        ordering = ["-start_date"]
        constraints = [
            # Identity includes `name` so named variants (e.g. "Reconducted Final
            # Exam") can coexist with the regular exam, while exact duplicates are
            # still blocked at the DB level.
            models.UniqueConstraint(
                fields=["academic_year", "program", "semester", "exam_type", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_exam_identity",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.program.code} Sem{self.semester.number})"


class ExamSchedule(BaseModel, SoftDeleteMixin):
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name="schedules"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="exam_schedules"
    )
    section = models.ForeignKey(
        Section, on_delete=models.PROTECT, related_name="exam_schedules"
    )
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name = "Exam Schedule"
        verbose_name_plural = "Exam Schedules"
        ordering = ["exam_date", "start_time"]
        constraints = [
            # Same subject for the same section in the same exam cannot repeat.
            models.UniqueConstraint(
                fields=["exam", "subject", "section"],
                condition=models.Q(is_deleted=False),
                name="unique_schedule_per_exam_subject_section",
            )
        ]

    def __str__(self):
        return f"{self.exam.name}: {self.subject.code} / {self.section.name} @ {self.exam_date}"


# =============================================================
# Mark (Sprint 9.2) — one student's result for one scheduled exam
# =============================================================
class Mark(BaseModel, SoftDeleteMixin):
    """
    Component marks are optional; `total_marks` is the computed sum.
    `grade` and `grade_point` are SNAPSHOTTED at entry time by the service
    (apps.exams.services.grade_for_marks) so historical results are immune to
    later grade-scale policy changes.
    """

    exam_schedule = models.ForeignKey(
        ExamSchedule, on_delete=models.PROTECT, related_name="marks"
    )
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="marks"
    )

    # Component marks (optional — a college may use only some of these).
    theory_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    practical_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    internal_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Computed + snapshotted by the service at entry time.
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=5, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    is_absent = models.BooleanField(default=False)

    # Entry metadata.
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="entered_marks",
    )
    entered_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Mark"
        verbose_name_plural = "Marks"
        ordering = ["student__student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam_schedule", "student"],
                condition=models.Q(is_deleted=False),
                name="unique_mark_per_student_per_schedule",
            )
        ]

    def __str__(self):
        return f"{self.student.student_id} - {self.exam_schedule.subject.code}: {self.total_marks} ({self.grade})"


# =============================================================
# Result (Sprint 9.3) — aggregated outcome for a student in an exam
# =============================================================
class Result(BaseModel, SoftDeleteMixin):
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="results"
    )
    exam = models.ForeignKey(
        Exam, on_delete=models.PROTECT, related_name="results"
    )

    gpa = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    cgpa = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_credits = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    earned_credits = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Result"
        verbose_name_plural = "Results"
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "exam"],
                condition=models.Q(is_deleted=False),
                name="unique_result_per_student_per_exam",
            )
        ]

    def __str__(self):
        return f"{self.student.student_id} / {self.exam.name}: GPA {self.gpa}"


class ResultItem(BaseModel, SoftDeleteMixin):
    """Snapshot of one subject's contribution to a Result (for transcripts/PDFs)."""

    result = models.ForeignKey(
        Result, on_delete=models.CASCADE, related_name="items"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="result_items"
    )
    marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=5, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    credits = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Result Item"
        verbose_name_plural = "Result Items"
        ordering = ["subject__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["result", "subject"],
                condition=models.Q(is_deleted=False),
                name="unique_result_item_per_subject",
            )
        ]

    def __str__(self):
        return f"{self.subject.code}: {self.grade} ({self.grade_point})"
