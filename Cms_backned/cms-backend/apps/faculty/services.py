"""
Faculty service layer.

Critical validation lives here (NOT in the model): before assigning a subject,
verify the Subject actually belongs to the Program + Semester via the curriculum
mapping (ProgramSemesterSubject). A teacher must not be assignable to a subject
that isn't part of that program/semester's curriculum.
"""

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.academics.models import ProgramSemesterSubject
from apps.accounts.services import assign_role
from apps.core.enums import AuditEvent, FacultyStatus, UserRole
from apps.core.exceptions import InvalidOperation, ValidationException
from apps.core.services import log_audit
from apps.faculty.models import Faculty, FacultyAssignment

User = get_user_model()


# =============================================================
# Validations
# =============================================================
def validate_subject_in_curriculum(program, semester, subject):
    """
    Subject must belong to Program + Semester through ProgramSemesterSubject.
    Blocks e.g. assigning a Semester-7 subject to a Semester-1 section.
    """
    in_curriculum = ProgramSemesterSubject.objects.filter(
        program=program, semester=semester, subject=subject
    ).exists()
    if not in_curriculum:
        raise ValidationException(
            f"{subject.code} is not part of the {program.code} "
            f"Semester {semester.number} curriculum."
        )


def _validate_section(program, semester, section):
    if section.program_id != program.id or section.semester_id != semester.id:
        raise ValidationException(
            "Section does not belong to the selected program and semester."
        )


# =============================================================
# Employee ID generation — SERVICE-ONLY
# =============================================================
def generate_employee_id(year: int) -> str:
    """
    Produce EMP-YYYY-XXXX with a per-year sequential counter.
    Must run inside a transaction; select_for_update guards concurrent creates,
    the DB unique constraint is the final backstop.
    """
    prefix = f"EMP-{year}-"
    last = (
        Faculty.all_objects.select_for_update()
        .filter(employee_id__startswith=prefix)
        .order_by("-employee_id")
        .first()
    )
    next_seq = (int(last.employee_id.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{next_seq:04d}"


# =============================================================
# Faculty creation
# =============================================================
@transaction.atomic
def create_faculty(*, account_email, password, join_date,
                   designation="", status=FacultyStatus.ACTIVE, actor=None):
    if User.all_objects.filter(email__iexact=account_email).exists():
        raise ValidationException("A user with this account email already exists.")

    employee_id = generate_employee_id(join_date.year)
    user = User.objects.create_user(email=account_email, password=password)
    faculty = Faculty.objects.create(
        user=user,
        employee_id=employee_id,
        designation=designation,
        join_date=join_date,
        status=status,
    )
    assign_role(user, UserRole.TEACHER)
    log_audit(
        action=AuditEvent.FACULTY_CREATED,
        actor=actor,
        instance=faculty,
        metadata={"employee_id": faculty.employee_id},
    )
    return faculty


# =============================================================
# Assignment
# =============================================================
@transaction.atomic
def assign_subject(*, faculty, academic_year, program, semester, section, subject, actor=None):
    """Assign a subject to a faculty for a section/term, with full validation."""
    _validate_section(program, semester, section)
    validate_subject_in_curriculum(program, semester, subject)

    if FacultyAssignment.objects.filter(
        academic_year=academic_year, program=program, semester=semester,
        section=section, subject=subject,
    ).exists():
        raise InvalidOperation(
            "This subject is already assigned for this section and term."
        )

    assignment = FacultyAssignment.objects.create(
        faculty=faculty,
        academic_year=academic_year,
        program=program,
        semester=semester,
        section=section,
        subject=subject,
    )
    log_audit(
        action=AuditEvent.SUBJECT_ASSIGNED,
        actor=actor,
        instance=faculty,
        metadata={
            "assignment_id": str(assignment.pk),
            "subject": subject.code,
            "program": program.code,
            "semester": semester.number,
            "section": section.name,
        },
    )
    return assignment


@transaction.atomic
def update_assignment(assignment, *, academic_year, program, semester, section, subject, actor=None):
    """Change an existing assignment's slot, re-running all validations."""
    _validate_section(program, semester, section)
    validate_subject_in_curriculum(program, semester, subject)

    clash = (
        FacultyAssignment.objects.filter(
            academic_year=academic_year, program=program, semester=semester,
            section=section, subject=subject,
        )
        .exclude(pk=assignment.pk)
        .exists()
    )
    if clash:
        raise InvalidOperation(
            "This subject is already assigned for this section and term."
        )

    assignment.academic_year = academic_year
    assignment.program = program
    assignment.semester = semester
    assignment.section = section
    assignment.subject = subject
    assignment.save(update_fields=["academic_year", "program", "semester",
                                   "section", "subject", "updated_at"])
    log_audit(
        action=AuditEvent.ASSIGNMENT_UPDATED,
        actor=actor,
        instance=assignment.faculty,
        metadata={"assignment_id": str(assignment.pk), "subject": subject.code,
                  "section": section.name},
    )
    return assignment


@transaction.atomic
def remove_assignment(assignment, actor=None):
    """Soft-remove a faculty assignment."""
    log_audit(
        action=AuditEvent.ASSIGNMENT_REMOVED,
        actor=actor,
        instance=assignment.faculty,
        metadata={"assignment_id": str(assignment.pk), "subject": assignment.subject.code},
    )
    assignment.delete()  # soft delete
    return True
