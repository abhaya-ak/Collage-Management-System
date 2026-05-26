# academics/services.py
"""
Academics domain service layer.

Existing functions (create_subject, update_subject, delete_subject,
get_subject, list_subjects, get_subjects_by_teacher) are preserved.

Added:
    AcademicsService — routine/exam validation
    ResultService    — grade computation, publish workflow
"""
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from subjects.models import Subject
from students.models import Teacher


# ─────────────────────────────────────────────────────────────────────────────
# Existing subject functions (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def create_subject(*, name: str, code: str, teacher_id: int = None) -> Subject:
    if Subject.objects.filter(code=code).exists():
        raise ValidationError({"code": f"A subject with the code '{code}' already exists."})
    teacher = None
    if teacher_id:
        try:
            teacher = Teacher.objects.get(id=teacher_id)
        except Teacher.DoesNotExist:
            raise ValidationError({"teacher": f"Teacher with ID {teacher_id} does not exist."})
    return Subject.objects.create(name=name, code=code, teacher=teacher)


def update_subject(*, subject: Subject, **data) -> Subject:
    new_code = data.get('code')
    if new_code and new_code != subject.code:
        if Subject.objects.filter(code=new_code).exclude(id=subject.id).exists():
            raise ValidationError({"code": f"A subject with the code '{new_code}' already exists."})
    if 'teacher_id' in data:
        teacher_id = data.pop('teacher_id')
        if teacher_id is None:
            subject.teacher = None
        else:
            try:
                subject.teacher = Teacher.objects.get(id=teacher_id)
            except Teacher.DoesNotExist:
                raise ValidationError({"teacher": f"Teacher with ID {teacher_id} does not exist."})
    for field, value in data.items():
        if hasattr(subject, field):
            setattr(subject, field, value)
    subject.save()
    return subject


def delete_subject(*, subject: Subject) -> None:
    subject.delete()


def get_subject(*, subject_id: int) -> Subject:
    try:
        return Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        raise ObjectDoesNotExist(f"Subject with ID {subject_id} not found.")


def list_subjects():
    return Subject.objects.select_related('teacher', 'teacher__user').all()


def get_subjects_by_teacher(*, teacher_id: int):
    return Subject.objects.select_related('teacher', 'teacher__user').filter(teacher_id=teacher_id)


# ─────────────────────────────────────────────────────────────────────────────
# AcademicsService — routine + exam scheduling rules
# ─────────────────────────────────────────────────────────────────────────────

class AcademicsService:

    @staticmethod
    def validate_faculty_name(name: str, exclude_pk: int | None = None) -> str:
        """
        Validates and normalises a Faculty name.

        Called from FacultyWriteSerializer.validate_name() on every
        faculty create and update.

        Steps (in order):
            1. Strip leading/trailing whitespace.
            2. Reject empty string after stripping.
            3. Enforce minimum length of 2 characters.
            4. Enforce maximum length of 100 characters (mirrors model field).
            5. Case-insensitive duplicate check — excludes own row on UPDATE.

        Args:
            name:        Raw name value from the serializer field.
            exclude_pk:  PK of the Faculty being updated; None on CREATE.
                         Prevents a PATCH from rejecting its own current name.

        Returns:
            Stripped name string — DRF stores this in validated_data.

        Raises:
            ValueError: Plain string; FacultyWriteSerializer converts to
                        serializers.ValidationError.  Do NOT raise
                        ValidationError here — services must stay framework-agnostic.
        """
        from .models import Faculty   # lazy import — avoids circular dependency

        # ── Step 1: normalise ─────────────────────────────────────────────────
        name = name.strip()

        # ── Step 2: empty guard ───────────────────────────────────────────────
        if not name:
            raise ValueError("Faculty name cannot be blank.")

        # ── Step 3: minimum length ────────────────────────────────────────────
        if len(name) < 2:
            raise ValueError("Faculty name must be at least 2 characters.")

        # ── Step 4: maximum length (belt-and-suspenders; mirrors max_length=100)
        if len(name) > 100:
            raise ValueError("Faculty name cannot exceed 100 characters.")

        # ── Step 5: case-insensitive uniqueness check ─────────────────────────
        qs = Faculty.objects.filter(name__iexact=name)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing:
            raise ValueError(
                f"A faculty named '{existing.name}' already exists."
            )

        return name

    @staticmethod
    def validate_time_range(start_time, end_time) -> None:
        if start_time and end_time and end_time <= start_time:
            raise ValueError("End time must be after start time.")

    @staticmethod
    def validate_room_not_conflicted(room, day_of_week, start_time, exclude_pk=None) -> None:
        from .models import Routine
        qs = Routine.objects.filter(
            room=room, day_of_week=day_of_week,
            start_time=start_time, is_active=True,
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            from .models import Routine as R
            day_label = R.Day(day_of_week).label if day_of_week is not None else day_of_week
            raise ValueError(
                f"Room '{room}' is already booked on {day_label} "
                f"at {start_time}. Choose a different room or time."
            )

    @staticmethod
    def validate_exam_date_not_past(exam_date) -> None:
        if exam_date < timezone.now().date():
            raise ValueError("Exam date cannot be in the past.")

    @staticmethod
    def validate_marks(full_marks, pass_marks) -> None:
        if full_marks and pass_marks and pass_marks >= full_marks:
            raise ValueError(
                f"Pass marks ({pass_marks}) must be strictly less than full marks ({full_marks})."
            )

    @staticmethod
    def validate_unique_exam_sitting(subject, exam_type, exam_date, exclude_pk=None) -> None:
        from .models import ExamRoutine
        qs = ExamRoutine.objects.filter(subject=subject, exam_type=exam_type, exam_date=exam_date)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValueError(f"A '{exam_type}' exam for this subject on {exam_date} already exists.")


# ─────────────────────────────────────────────────────────────────────────────
# ResultService — grade computation, result entry, publish
# ─────────────────────────────────────────────────────────────────────────────

class ResultService:

    GRADE_BOUNDARIES = [
        (90, 'A+'), (80, 'A'), (70, 'B+'),
        (60, 'B'),  (50, 'C'), (40, 'D'), (0, 'F'),
    ]

    @staticmethod
    def compute_grade(marks_obtained: int, full_marks: int) -> str:
        """Auto-compute letter grade from percentage."""
        if not full_marks:
            return 'F'
        pct = (marks_obtained / full_marks) * 100
        for threshold, grade in ResultService.GRADE_BOUNDARIES:
            if pct >= threshold:
                return grade
        return 'F'

    @staticmethod
    def is_passed(result) -> bool:
        """Returns True if student passed (not absent, marks >= pass_marks)."""
        if result.is_absent:
            return False
        return result.marks_obtained >= result.exam_routine.pass_marks

    @staticmethod
    def validate_absent_marks(is_absent: bool, marks_obtained) -> None:
        if is_absent and marks_obtained and marks_obtained != 0:
            raise ValueError(
                "Student is marked absent. marks_obtained must be 0 for absent students."
            )

    @staticmethod
    def validate_marks_in_range(marks_obtained, full_marks, is_absent=False) -> None:
        if is_absent:
            return
        if marks_obtained is None or full_marks is None:
            return
        if marks_obtained < 0:
            raise ValueError("Marks cannot be negative.")
        if marks_obtained > full_marks:
            raise ValueError(
                f"Marks obtained ({marks_obtained}) cannot exceed "
                f"full marks ({full_marks}) for this exam."
            )

    @staticmethod
    def validate_unique_result(student, exam_routine, exclude_pk=None) -> None:
        from .models import Result
        qs = Result.objects.filter(student=student, exam_routine=exam_routine)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValueError(
                "A result for this student and exam already exists. "
                "Use the update endpoint to correct it."
            )

    @staticmethod
    def validate_not_already_published(result) -> None:
        if result.is_published:
            raise ValueError("Result is already published.")

    @staticmethod
    def validate_retraction_not_allowed(result, new_value: bool) -> None:
        if result and result.is_published and not new_value:
            raise ValueError(
                "A published result cannot be retracted here. "
                "Contact a system administrator."
            )

    @staticmethod
    @transaction.atomic
    def publish(result) -> object:
        """Publishes a result. Raises ValueError if already published."""
        ResultService.validate_not_already_published(result)
        result.is_published = True
        result.save(update_fields=['is_published'])
        return result