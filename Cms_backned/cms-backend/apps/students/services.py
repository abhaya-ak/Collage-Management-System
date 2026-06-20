"""
Services — write-side business logic for the students domain.

    AdmissionService:   admit_student()            (one transaction)
    EnrollmentService:  enroll_student / promote_student / change_section
    ID generation:      generate_student_id()      (SERVICE-ONLY)

Rules enforced here:
    * student_id is minted only in this layer (STU-YYYY-XXXX)
    * only ONE active enrollment per student
    * promotion preserves history (old ACTIVE -> PROMOTED, new ACTIVE created)
"""

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.services import assign_role
from apps.core.enums import AuditEvent, EnrollmentStatus, UserRole
from apps.core.exceptions import InvalidOperation, ValidationException
from apps.core.services import log_audit
from apps.students.models import Student, StudentEnrollment
from apps.students.selectors import get_active_enrollment

User = get_user_model()


# =============================================================
# Student ID generation — SERVICE-ONLY
# =============================================================
def generate_student_id(year: int) -> str:
    """
    Produce STU-YYYY-XXXX with a per-year sequential counter.

    Must run inside a transaction (admit_student provides one). select_for_update
    locks existing rows for the year so concurrent admissions don't collide; the
    DB unique constraint is the final backstop.
    """
    prefix = f"STU-{year}-"
    last = (
        Student.all_objects.select_for_update()
        .filter(student_id__startswith=prefix)
        .order_by("-student_id")
        .first()
    )
    next_seq = (int(last.student_id.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{next_seq:04d}"


# =============================================================
# Admission Service — the core flow
# =============================================================
@transaction.atomic
def admit_student(*, account_email, password, registration_number, profile, enrollment, actor=None):
    """
    One transaction:
      1. create CustomUser
      2. create Student (+ generated student_id)
      3. create initial ACTIVE StudentEnrollment
      4. assign default role STUDENT
    """
    if User.all_objects.filter(email__iexact=account_email).exists():
        raise ValidationException("A user with this account email already exists.")
    if Student.all_objects.filter(registration_number=registration_number).exists():
        raise ValidationException("A student with this registration number already exists.")

    user = User.objects.create_user(
        email=account_email,
        password=password,
        first_name=profile.get("first_name", ""),
        last_name=profile.get("last_name", ""),
    )

    student_id = generate_student_id(profile["admission_date"].year)
    student = Student.objects.create(
        user=user,
        student_id=student_id,
        registration_number=registration_number,
        **profile,
    )

    initial = StudentEnrollment.objects.create(
        student=student, status=EnrollmentStatus.ACTIVE, **enrollment
    )

    assign_role(user, UserRole.STUDENT)
    log_audit(
        action=AuditEvent.STUDENT_ADMITTED,
        actor=actor,
        instance=student,
        metadata={
            "student_id": student.student_id,
            "registration_number": student.registration_number,
            "enrollment_id": str(initial.pk),
        },
    )
    return student


# =============================================================
# Enrollment Service
# =============================================================
def _validate_section(program, semester, section):
    if section.program_id != program.id or section.semester_id != semester.id:
        raise ValidationException(
            "Section does not belong to the selected program and semester."
        )


@transaction.atomic
def enroll_student(student, *, academic_year, program, semester, section, enrollment_date, actor=None):
    """Create a fresh ACTIVE enrollment. Fails if one is already active."""
    if get_active_enrollment(student):
        raise InvalidOperation(
            "Student already has an active enrollment. Use promote instead."
        )
    _validate_section(program, semester, section)
    enrollment = StudentEnrollment.objects.create(
        student=student,
        academic_year=academic_year,
        program=program,
        semester=semester,
        section=section,
        status=EnrollmentStatus.ACTIVE,
        enrollment_date=enrollment_date,
    )
    log_audit(
        action=AuditEvent.ENROLLMENT_CREATED,
        actor=actor,
        instance=student,
        metadata={"enrollment_id": str(enrollment.pk), "program": program.code,
                  "semester": semester.number, "section": section.name},
    )
    return enrollment


@transaction.atomic
def promote_student(student, *, academic_year, program, semester, section, enrollment_date, actor=None):
    """Deactivate the current ACTIVE enrollment (-> PROMOTED) and create a new ACTIVE one."""
    _validate_section(program, semester, section)
    active = get_active_enrollment(student)
    if active:
        active.status = EnrollmentStatus.PROMOTED
        active.save(update_fields=["status", "updated_at"])

    new_enrollment = StudentEnrollment.objects.create(
        student=student,
        academic_year=academic_year,
        program=program,
        semester=semester,
        section=section,
        status=EnrollmentStatus.ACTIVE,
        enrollment_date=enrollment_date,
    )
    log_audit(
        action=AuditEvent.STUDENT_PROMOTED,
        actor=actor,
        instance=student,
        changes={
            "from_enrollment": str(active.pk) if active else None,
            "to_enrollment": str(new_enrollment.pk),
        },
        metadata={"program": program.code, "semester": semester.number,
                  "section": section.name},
    )
    return new_enrollment


@transaction.atomic
def change_section(student, section, actor=None):
    """Move the active enrollment to a different section (same program/semester)."""
    active = get_active_enrollment(student)
    if not active:
        raise InvalidOperation("Student has no active enrollment.")
    _validate_section(active.program, active.semester, section)
    old_section = active.section
    active.section = section
    active.save(update_fields=["section", "updated_at"])
    log_audit(
        action=AuditEvent.SECTION_CHANGED,
        actor=actor,
        instance=student,
        changes={"section": {"from": old_section.name, "to": section.name}},
        metadata={"enrollment_id": str(active.pk)},
    )
    return active