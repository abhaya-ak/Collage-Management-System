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

import logging
import re
import secrets
import string

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.academics.models import Section, Semester
from apps.academics.selectors import get_current_academic_year
from apps.accounts.email_service import send_student_credentials
from apps.accounts.services import assign_role
from apps.core.enums import AuditEvent, EnrollmentStatus, UserRole
from apps.core.exceptions import InvalidOperation, ValidationException
from apps.core.services import log_audit
from apps.students.models import Student, StudentEnrollment
from apps.students.selectors import get_active_enrollment

User = get_user_model()
logger = logging.getLogger(__name__)


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
# Institutional login email generation — SERVICE-ONLY
# =============================================================
EMAIL_DOMAIN = "college.edu"


def _name_to_local_part(*name_parts) -> str:
    """
    Normalize name parts into an email local part:
      lowercase, trim, strip special chars, collapse spaces -> dot-separated.
      "Ram  Bahadur", "Sharma" -> "ram.bahadur.sharma"
    """
    text = " ".join(p for p in name_parts if p).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)   # drop special characters
    tokens = text.split()                     # collapses multiple spaces
    return ".".join(tokens)


def generate_account_email(first_name: str, last_name: str) -> str:
    """
    Generate a unique institutional login email from the student's name.
    Uniqueness is checked against ALL users (including soft-deleted) and a
    numeric suffix is appended until free:
        ram.sharma@college.edu -> ram.sharma1@college.edu -> ram.sharma2@...
    """
    base = _name_to_local_part(first_name, last_name) or "student"
    candidate = f"{base}@{EMAIL_DOMAIN}"
    suffix = 0
    while User.all_objects.filter(email__iexact=candidate).exists():
        suffix += 1
        candidate = f"{base}{suffix}@{EMAIL_DOMAIN}"
    return candidate


def generate_temporary_password(length: int = 10) -> str:
    """
    Generate a strong random temporary password (returned once to the admin).
    Guarantees at least one lowercase, uppercase, digit, and symbol so it passes
    typical password validators; the student changes it on first login.
    """
    alphabet = string.ascii_letters + string.digits
    symbols = "@#$%&*"
    while True:
        core = "".join(secrets.choice(alphabet) for _ in range(length - 1))
        pw = core + secrets.choice(symbols)
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw)):
            return pw


# =============================================================
# Section allocation helper
# =============================================================
def find_available_section(*, program, semester) -> Section:
    """
    Alphabetically scan sections for the given program + semester and return
    the first one that has capacity remaining (active enrolments < capacity).

    Rules:
      - Sections are ordered alphabetically by name (A before B before C…).
      - Only non-deleted active StudentEnrollments count toward capacity.
      - Soft-deleted enrolments are excluded automatically (SoftDeleteMixin
        manager filters them out).
      - Raises ValidationException if every section is at capacity so the
        admin knows to create a new section.
    """
    sections = (
        Section.objects
        .filter(program=program, semester=semester)
        .order_by("name")          # A, B, C …
    )
    if not sections.exists():
        raise ValidationException(
            f"No sections found for {program.code} Semester {semester.number}. "
            "Please create at least one section before admitting students."
        )

    for section in sections:
        active_count = StudentEnrollment.objects.filter(
            section=section,
            status=EnrollmentStatus.ACTIVE,
        ).count()
        if section.capacity > 0 and active_count < section.capacity:
            return section

    raise ValidationException(
        f"No available section capacity for {program.code} "
        f"Semester {semester.number}. "
        "All sections are full — please create a new section."
    )


# =============================================================
# Admission Service — the core flow
# =============================================================
@transaction.atomic
def admit_student(*, registration_number, profile, program, actor=None):
    """
    One transaction:
      1. Validate uniqueness
      2. Generate institutional login email + temporary password + create CustomUser
      3. Generate student_id
      4. Create Student profile
      5. Auto-resolve: current academic year, Semester 1, available section
      6. Create initial ACTIVE StudentEnrollment
      7. Assign STUDENT role
      8. Audit log

    Returns the Student with a transient `temporary_password` attribute (the
    plaintext is never stored — surfaced once for the admin to relay).
    """
    if Student.all_objects.filter(registration_number=registration_number).exists():
        raise ValidationException("A student with this registration number already exists.")

    # Login email + temporary password are generated by the system.
    account_email = generate_account_email(
        profile.get("first_name", ""), profile.get("last_name", "")
    )
    password = generate_temporary_password()

    # --- auto-resolve enrollment context ---------------------------------
    academic_year = get_current_academic_year()

    semester = Semester.objects.filter(number=1).first()
    if semester is None:
        raise InvalidOperation(
            "Semester 1 does not exist. Please create semesters before admitting students."
        )

    section = find_available_section(program=program, semester=semester)
    # Admission, enrollment, and section placement happen together:
    # enrollment_date is always the admission date.
    enrollment_date = profile["admission_date"]
    # ---------------------------------------------------------------------

    user = User.objects.create_user(
        email=account_email,
        password=password,
        first_name=profile.get("first_name", ""),
        last_name=profile.get("last_name", ""),
        must_change_password=True,  # force change of the temporary password
    )

    student_id = generate_student_id(profile["admission_date"].year)
    student = Student.objects.create(
        user=user,
        student_id=student_id,
        registration_number=registration_number,
        **profile,
    )

    initial = StudentEnrollment.objects.create(
        student=student,
        academic_year=academic_year,
        program=program,
        semester=semester,
        section=section,
        status=EnrollmentStatus.ACTIVE,
        enrollment_date=enrollment_date,
    )

    assign_role(user, UserRole.STUDENT)
    log_audit(
        action=AuditEvent.STUDENT_ADMITTED,
        actor=actor,
        instance=student,
        metadata={
            "student_id": student.student_id,
            "registration_number": student.registration_number,
            "academic_year": academic_year.name,
            "program": program.code,
            "semester": semester.number,
            "section": section.name,
            "enrollment_id": str(initial.pk),
        },
    )
    # Send credentials ONLY after the transaction commits (never before) so we
    # never email a student whose admission was rolled back. Email failure is
    # logged but must not fail the admission.
    def _send_credentials():
        try:
            send_student_credentials(
                to_email=student.email,
                student_name=student.full_name,
                student_id=student.student_id,
                login_email=account_email,
                temporary_password=password,
            )
        except Exception:  # noqa: BLE001 — best-effort; admission already committed
            logger.exception(
                "Failed to send credentials email for %s", student.student_id
            )

    transaction.on_commit(_send_credentials)

    # Transient (not persisted) — surfaced once in the admission response.
    student.temporary_password = password
    return student


@transaction.atomic
def resend_credentials(student, *, actor=None):
    """
    Admin re-issues a student's credentials: generates a NEW temporary password
    (the original is hashed and unrecoverable), forces a change on next login,
    and re-sends the welcome email. Returns the student with a transient
    `temporary_password`.
    """
    user = student.user
    new_password = generate_temporary_password()
    user.set_password(new_password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password", "updated_at"])

    def _send():
        try:
            send_student_credentials(
                to_email=student.email,
                student_name=student.full_name,
                student_id=student.student_id,
                login_email=user.email,
                temporary_password=new_password,
            )
        except Exception:  # noqa: BLE001 — best-effort
            logger.exception("Failed to resend credentials for %s", student.student_id)

    transaction.on_commit(_send)
    log_audit(
        action=AuditEvent.CREDENTIALS_RESENT, actor=actor, instance=student,
        metadata={"student_id": student.student_id, "login_email": user.email},
    )
    student.temporary_password = new_password
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