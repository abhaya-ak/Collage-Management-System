"""
Grading engine — the single source of truth for marks -> grade/point and
GPA/CGPA computation. Everything in the exam/result domain calls these.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.enums import AuditEvent, ExamType
from apps.core.exceptions import (
    InvalidOperation,
    PermissionDeniedException,
    ValidationException,
)
from apps.core.services import log_audit
from apps.exams.models import GradeScale, Mark, Result, ResultItem
from apps.faculty.models import Faculty, FacultyAssignment
from apps.faculty.services import validate_subject_in_curriculum
from apps.students.models import StudentEnrollment

_TWO = Decimal("0.01")


def get_grade_scale(marks) -> GradeScale:
    """Return the GradeScale row whose range contains `marks`, or raise."""
    marks = Decimal(str(marks))
    scale = GradeScale.objects.filter(
        min_marks__lte=marks, max_marks__gte=marks
    ).first()
    if scale is None:
        raise ValidationException(f"No grade scale configured for marks {marks}.")
    return scale


def grade_for_marks(marks):
    """Resolve (grade, grade_point, is_passing) for a marks value."""
    scale = get_grade_scale(marks)
    return scale.grade, scale.grade_point, scale.is_passing


def compute_gpa(items) -> Decimal:
    """
    Credit-weighted GPA from [(grade_point, credit_hours), ...].
    GPA = Σ(grade_point × credit) / Σ(credit).
    """
    total_credits = Decimal("0")
    weighted = Decimal("0")
    for grade_point, credit_hours in items:
        gp = Decimal(str(grade_point))
        ch = Decimal(str(credit_hours))
        weighted += gp * ch
        total_credits += ch
    if total_credits == 0:
        return Decimal("0.00")
    return (weighted / total_credits).quantize(_TWO, rounding=ROUND_HALF_UP)


def compute_cgpa(semester_gpas) -> Decimal:
    """
    CGPA across semesters from [(gpa, total_credits), ...].
    Credit-weighted average of semester GPAs.
    """
    return compute_gpa(semester_gpas)


# =============================================================
# Marks entry (Sprint 9.2)
# =============================================================
def _authorize_marks(user, exam_schedule):
    """Only the teacher assigned to this subject+section (or a manager) may enter marks."""
    if user is None:
        return
    if user.is_superuser or user.has_permission("manage_marks"):
        return
    faculty = Faculty.objects.filter(user=user).first()
    exam = exam_schedule.exam
    assigned = faculty and FacultyAssignment.objects.filter(
        faculty=faculty,
        academic_year=exam.academic_year,
        program=exam.program,
        semester=exam.semester,
        section=exam_schedule.section,
        subject=exam_schedule.subject,
    ).exists()
    if not assigned:
        raise PermissionDeniedException(
            "You can only enter marks for subjects/sections you are assigned to teach."
        )


def _validate_student_in_section(student, section):
    if not StudentEnrollment.objects.filter(
        student=student, section=section, status="ACTIVE"
    ).exists():
        raise ValidationException(
            f"{student.student_id} is not actively enrolled in this section."
        )


@transaction.atomic
def enter_marks(*, exam_schedule, student, theory_marks=None, practical_marks=None,
                internal_marks=None, is_absent=False, actor=None):
    """
    Enter (or update) one student's marks for a scheduled exam.

    Steps:
      1. authorize teacher
      2. validate student belongs to the section
      3. validate subject belongs to the curriculum (Program + Semester)
      4. compute total
      5. resolve grade + grade_point and SNAPSHOT them onto the row
      6. save (blocked if already published)
    """
    _authorize_marks(actor, exam_schedule)
    _validate_student_in_section(student, exam_schedule.section)

    exam = exam_schedule.exam
    validate_subject_in_curriculum(exam.program, exam.semester, exam_schedule.subject)

    existing = Mark.objects.filter(exam_schedule=exam_schedule, student=student).first()
    if existing and existing.is_published:
        raise InvalidOperation("Marks are already published and cannot be edited.")

    components = [theory_marks, practical_marks, internal_marks]
    if not is_absent and all(c is None for c in components):
        raise ValidationException("Provide at least one marks component, or mark the student absent.")

    total = Decimal("0") if is_absent else sum(
        (Decimal(str(c)) for c in components if c is not None), Decimal("0")
    )
    grade, grade_point, _passing = grade_for_marks(total)  # snapshot at entry time

    mark, _ = Mark.objects.update_or_create(
        exam_schedule=exam_schedule,
        student=student,
        defaults={
            "theory_marks": theory_marks,
            "practical_marks": practical_marks,
            "internal_marks": internal_marks,
            "total_marks": total,
            "grade": grade,
            "grade_point": grade_point,
            "is_absent": is_absent,
            "entered_by": actor if getattr(actor, "pk", None) else None,
            "entered_at": timezone.now(),
        },
    )
    log_audit(
        action=AuditEvent.MARKS_ENTERED,
        actor=actor,
        instance=mark,
        metadata={
            "student_id": student.student_id,
            "subject": exam_schedule.subject.code,
            "total": str(total),
            "grade": grade,
            "is_absent": is_absent,
        },
    )
    return mark


# =============================================================
# Result generation & publishing (Sprint 9.3)
# =============================================================
@transaction.atomic
def generate_result(*, student, exam, actor=None):
    """
    Aggregate a student's marks for an exam into a Result + ResultItems.
    Re-runnable (regenerates) until published.
    """
    marks = list(
        Mark.objects.filter(exam_schedule__exam=exam, student=student)
        .select_related("exam_schedule__subject")
    )
    if not marks:
        raise ValidationException("No marks found for this student in this exam.")

    existing = Result.objects.filter(student=student, exam=exam).first()
    if existing and existing.published:
        raise InvalidOperation("Result is already published and cannot be regenerated.")

    gpa_input, total_credits, earned_credits, items = [], Decimal("0"), Decimal("0"), []
    for m in marks:
        subject = m.exam_schedule.subject
        credits = Decimal(str(subject.credit_hours))
        gp = m.grade_point or Decimal("0")
        gpa_input.append((gp, credits))
        total_credits += credits
        if gp > 0:                                   # passing subject -> credits earned
            earned_credits += credits
        items.append((subject, m.total_marks, m.grade, gp, credits))

    gpa = compute_gpa(gpa_input)

    result, _ = Result.objects.update_or_create(
        student=student, exam=exam,
        defaults={
            "gpa": gpa,
            "total_credits": total_credits,
            "earned_credits": earned_credits,
            "generated_at": timezone.now(),
        },
    )

    # CGPA = credit-weighted average across the student's FINAL_TERM results only.
    # Mid-Term (and other) exams are informational and do not contribute to CGPA;
    # this avoids double-counting a semester. A Mid-Term result will therefore show
    # the official CGPA earned from completed (final-term) semesters so far.
    final_results = Result.objects.filter(
        student=student, exam__exam_type=ExamType.FINAL_TERM
    )
    result.cgpa = compute_cgpa([(r.gpa, r.total_credits) for r in final_results])
    result.save(update_fields=["cgpa", "updated_at"])

    # Rebuild item snapshots.
    result.items.all().delete()  # soft delete previous snapshot
    for subject, marks_val, grade, gp, credits in items:
        ResultItem.objects.create(
            result=result, subject=subject, marks=marks_val,
            grade=grade, grade_point=gp, credits=credits,
        )

    log_audit(
        action=AuditEvent.RESULT_GENERATED,
        actor=actor,
        instance=result,
        metadata={"exam": exam.name, "gpa": str(gpa), "cgpa": str(result.cgpa),
                  "subjects": len(items)},
    )
    return result


@transaction.atomic
def publish_result(result, actor=None):
    """Publish a result and lock its underlying marks. Separate from generation."""
    if result.published:
        raise InvalidOperation("Result is already published.")
    result.published = True
    result.published_at = timezone.now()
    result.save(update_fields=["published", "published_at", "updated_at"])

    # Lock the marks behind this result.
    Mark.objects.filter(
        exam_schedule__exam=result.exam, student=result.student
    ).update(is_published=True)

    log_audit(
        action=AuditEvent.RESULT_PUBLISHED,
        actor=actor,
        instance=result,
        metadata={"exam": result.exam.name, "gpa": str(result.gpa)},
    )
    return result
