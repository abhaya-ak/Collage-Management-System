"""
Step 4 — System-wide enums.

Centralized choice definitions so values are never hardcoded across apps.
Always import from here:  from apps.core.enums import UserRole
"""

from django.db.models import TextChoices


class UserRole(TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    ADMIN = "ADMIN", "Admin"
    TEACHER = "TEACHER", "Teacher"
    ACCOUNTANT = "ACCOUNTANT", "Accountant"
    STUDENT = "STUDENT", "Student"


class AttendanceStatus(TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"
    LEAVE = "LEAVE", "Leave"


class FeeStatus(TextChoices):
    PENDING = "PENDING", "Pending"
    PARTIAL = "PARTIAL", "Partial"
    PAID = "PAID", "Paid"


class StudentStatus(TextChoices):
    ACTIVE = "ACTIVE", "Active"
    GRADUATED = "GRADUATED", "Graduated"
    DROPPED = "DROPPED", "Dropped"
    SUSPENDED = "SUSPENDED", "Suspended"


class ExamStatus(TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED = "ARCHIVED", "Archived"


class ExamType(TextChoices):
    MID_TERM = "MID_TERM", "Mid Term"
    FINAL_TERM = "FINAL_TERM", "Final Term"
    BACK_EXAM = "BACK_EXAM", "Back Exam"
    PRACTICAL_EXAM = "PRACTICAL_EXAM", "Practical Exam"


class Gender(TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"
    OTHER = "OTHER", "Other"


class DocumentType(TextChoices):
    SEE_CERTIFICATE = "SEE_CERTIFICATE", "SEE Certificate"
    PLUS_TWO_CERTIFICATE = "PLUS_TWO_CERTIFICATE", "+2 Certificate"
    CITIZENSHIP = "CITIZENSHIP", "Citizenship"
    MIGRATION = "MIGRATION", "Migration Certificate"
    CHARACTER = "CHARACTER", "Character Certificate"
    PHOTO = "PHOTO", "Passport Photo"


class EnrollmentStatus(TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PROMOTED = "PROMOTED", "Promoted"
    GRADUATED = "GRADUATED", "Graduated"
    DROPPED = "DROPPED", "Dropped"


class FacultyStatus(TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ON_LEAVE = "ON_LEAVE", "On Leave"
    RESIGNED = "RESIGNED", "Resigned"
    RETIRED = "RETIRED", "Retired"
    SUSPENDED = "SUSPENDED", "Suspended"


class AuditEvent(TextChoices):
    """
    Centralized audit/event names. Stored on AuditLog.action.
    Semantic domain events double as the system's event log.
    """

    # generic
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    # accounts domain
    PROFILE_UPDATED = "profile_updated", "Profile Updated"
    # students domain
    STUDENT_ADMITTED = "student_admitted", "Student Admitted"
    STUDENT_PROMOTED = "student_promoted", "Student Promoted"
    ENROLLMENT_CREATED = "enrollment_created", "Enrollment Created"
    SECTION_CHANGED = "section_changed", "Section Changed"
    # faculty domain
    FACULTY_CREATED = "faculty_created", "Faculty Created"
    SUBJECT_ASSIGNED = "subject_assigned", "Subject Assigned"
    ASSIGNMENT_UPDATED = "assignment_updated", "Assignment Updated"
    ASSIGNMENT_REMOVED = "assignment_removed", "Assignment Removed"
    # attendance domain
    ATTENDANCE_SESSION_CREATED = "attendance_session_created", "Attendance Session Created"
    ATTENDANCE_MARKED = "attendance_marked", "Attendance Marked"
    ATTENDANCE_UPDATED = "attendance_updated", "Attendance Updated"
    ATTENDANCE_LOCKED = "attendance_locked", "Attendance Locked"
    # exams domain
    MARKS_ENTERED = "marks_entered", "Marks Entered"
    RESULT_GENERATED = "result_generated", "Result Generated"
    RESULT_PUBLISHED = "result_published", "Result Published"
