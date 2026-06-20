"""
Attendance service layer — enforces the business rules.

Rule 1: a teacher may only manage attendance for their assigned classes.
Rule 2: a student must belong to the session's section (active enrollment).
Rule 3: only one session per class per day (DB constraint + friendly pre-check).
Rule 4: a locked session cannot be edited.
"""

from django.db import transaction

from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.core.enums import AuditEvent
from apps.core.exceptions import (
    InvalidOperation,
    PermissionDeniedException,
    ValidationException,
)
from apps.core.services import log_audit
from apps.faculty.models import Faculty
from apps.students.models import StudentEnrollment


# =============================================================
# Authorization & validation helpers
# =============================================================
def _authorize(user, assignment):
    """Rule 1 — only the assigned teacher (or a manager/superuser) may proceed."""
    if user.is_superuser or user.has_permission("manage_attendance"):
        return
    faculty = Faculty.objects.filter(user=user).first()
    if faculty and assignment.faculty_id == faculty.id:
        return
    raise PermissionDeniedException(
        "You can only manage attendance for your assigned classes."
    )


def _validate_student_in_section(student, section):
    """Rule 2 — student must have an ACTIVE enrollment in the session's section."""
    ok = StudentEnrollment.objects.filter(
        student=student, section=section, status="ACTIVE"
    ).exists()
    if not ok:
        raise ValidationException(
            f"{student.student_id} is not actively enrolled in this section."
        )


# =============================================================
# Services
# =============================================================
@transaction.atomic
def create_session(*, faculty_assignment, attendance_date, remarks="", actor=None):
    _authorize(actor, faculty_assignment)

    # Rule 3 — friendly pre-check (DB constraint is the backstop).
    if AttendanceSession.objects.filter(
        faculty_assignment=faculty_assignment, attendance_date=attendance_date
    ).exists():
        raise InvalidOperation(
            "An attendance session already exists for this class on this date."
        )

    session = AttendanceSession.objects.create(
        faculty_assignment=faculty_assignment,
        attendance_date=attendance_date,
        remarks=remarks,
    )
    log_audit(
        action=AuditEvent.ATTENDANCE_SESSION_CREATED,
        actor=actor,
        instance=session,
        metadata={"assignment_id": str(faculty_assignment.pk),
                  "date": str(attendance_date)},
    )
    return session


@transaction.atomic
def mark_attendance(session, records, actor=None):
    """
    Upsert per-student records for a session.
    `records` = [{"student": <Student>, "status": "PRESENT"}, ...]
    """
    if session.is_locked:                                   # Rule 4
        raise InvalidOperation("This attendance session is locked and cannot be edited.")

    _authorize(actor, session.faculty_assignment)           # Rule 1
    section = session.faculty_assignment.section

    had_records = session.records.exists()
    created, updated = 0, 0
    for row in records:
        student, status = row["student"], row["status"]
        _validate_student_in_section(student, section)      # Rule 2
        _, was_created = AttendanceRecord.objects.update_or_create(
            session=session, student=student, defaults={"status": status}
        )
        created += int(was_created)
        updated += int(not was_created)

    event = AuditEvent.ATTENDANCE_UPDATED if had_records else AuditEvent.ATTENDANCE_MARKED
    log_audit(
        action=event,
        actor=actor,
        instance=session,
        metadata={"created": created, "updated": updated, "total": len(records)},
    )
    return session


@transaction.atomic
def lock_session(session, actor=None):
    if session.is_locked:
        raise InvalidOperation("This attendance session is already locked.")
    _authorize(actor, session.faculty_assignment)
    session.is_locked = True
    session.save(update_fields=["is_locked", "updated_at"])
    log_audit(
        action=AuditEvent.ATTENDANCE_LOCKED,
        actor=actor,
        instance=session,
        metadata={"record_count": session.records.count()},
    )
    return session
