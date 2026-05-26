# users/constants.py

class RoleNames:
    """
    Canonical role name strings.

    These match the `name` field on the users.Role model exactly.
    The seed_roles command creates Role objects using these strings.
    AuthService, views, and permissions import from here — never hardcode.
    """
    SUPER_ADMIN   = 'super_admin'
    ADMIN         = 'admin'
    TEACHER       = 'teacher'
    STUDENT       = 'student'
    ACCOUNTS      = 'accounts'
    FINANCE       = 'finance'
    RECEPTIONIST  = 'receptionist'

    # Convenience tuple for iteration (e.g. validation, admin display)
    ALL = (
        SUPER_ADMIN,
        ADMIN,
        TEACHER,
        STUDENT,
        ACCOUNTS,
        FINANCE,
        RECEPTIONIST,
    )


class PermissionCodes:
    """
    Canonical permission code strings.

    Format convention: '<module>.<action>_<resource>'
    These must match the `code` field on the users.Permission model exactly.

    Grouped by module for readability.
    """

    # ── Academics ────────────────────────────────────────────────────────────
    ACADEMICS_VIEW_RESULT        = 'academics.view_result'
    ACADEMICS_MANAGE_RESULT      = 'academics.manage_result'
    ACADEMICS_VIEW_TIMETABLE     = 'academics.view_timetable'
    ACADEMICS_MANAGE_TIMETABLE   = 'academics.manage_timetable'

    # ── Attendance ───────────────────────────────────────────────────────────
    ATTENDANCE_MARK              = 'attendance.mark_attendance'
    ATTENDANCE_VIEW_OWN          = 'attendance.view_own_attendance'
    ATTENDANCE_VIEW_ALL          = 'attendance.view_all_attendance'

    # ── Fees ─────────────────────────────────────────────────────────────────
    FEES_VIEW_OWN                = 'fees.view_own_fees'
    FEES_VIEW_ALL                = 'fees.view_all_fees'
    FEES_SUBMIT_PAYMENT          = 'fees.submit_payment'
    FEES_VERIFY_PAYMENT          = 'fees.verify_payment'
    FEES_MANAGE                  = 'fees.manage_fees'

    # ── Students ─────────────────────────────────────────────────────────────
    STUDENTS_VIEW_OWN            = 'students.view_own_profile'
    STUDENTS_VIEW_ALL            = 'students.view_all_students'
    STUDENTS_MANAGE              = 'students.manage_students'

    # ── Notices ──────────────────────────────────────────────────────────────
    NOTICES_VIEW                 = 'notices.view_notice'
    NOTICES_MANAGE               = 'notices.manage_notice'

    # ── Feedback ─────────────────────────────────────────────────────────────
    FEEDBACK_SUBMIT              = 'feedback.submit_feedback'
    FEEDBACK_VIEW_ALL            = 'feedback.view_all_feedback'

    # ── Subjects ─────────────────────────────────────────────────────────────
    SUBJECTS_VIEW                = 'subjects.view_subject'
    SUBJECTS_MANAGE              = 'subjects.manage_subject'

    # ── Users / Admin ─────────────────────────────────────────────────────────
    USERS_VIEW_ALL               = 'users.view_all_users'
    USERS_MANAGE                 = 'users.manage_users'

ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    RoleNames.ADMIN: [
        PermissionCodes.ACADEMICS_VIEW_RESULT,
        PermissionCodes.ACADEMICS_MANAGE_RESULT,
        PermissionCodes.ACADEMICS_VIEW_TIMETABLE,
        PermissionCodes.ACADEMICS_MANAGE_TIMETABLE,
        PermissionCodes.ATTENDANCE_MARK,
        PermissionCodes.ATTENDANCE_VIEW_ALL,
        PermissionCodes.FEES_VIEW_ALL,
        PermissionCodes.FEES_VERIFY_PAYMENT,
        PermissionCodes.FEES_MANAGE,
        PermissionCodes.STUDENTS_VIEW_ALL,
        PermissionCodes.STUDENTS_MANAGE,
        PermissionCodes.NOTICES_VIEW,
        PermissionCodes.NOTICES_MANAGE,
        PermissionCodes.FEEDBACK_VIEW_ALL,
        PermissionCodes.SUBJECTS_VIEW,
        PermissionCodes.SUBJECTS_MANAGE,
        PermissionCodes.USERS_VIEW_ALL,
        PermissionCodes.USERS_MANAGE,
    ],
    RoleNames.TEACHER: [
        PermissionCodes.ACADEMICS_VIEW_RESULT,
        PermissionCodes.ACADEMICS_MANAGE_RESULT,
        PermissionCodes.ACADEMICS_VIEW_TIMETABLE,
        PermissionCodes.ATTENDANCE_MARK,
        PermissionCodes.ATTENDANCE_VIEW_ALL,
        PermissionCodes.STUDENTS_VIEW_ALL,
        PermissionCodes.NOTICES_VIEW,
        PermissionCodes.SUBJECTS_VIEW,
        PermissionCodes.FEEDBACK_VIEW_ALL,
    ],
    RoleNames.STUDENT: [
        PermissionCodes.ACADEMICS_VIEW_RESULT,
        PermissionCodes.ACADEMICS_VIEW_TIMETABLE,
        PermissionCodes.ATTENDANCE_VIEW_OWN,
        PermissionCodes.FEES_VIEW_OWN,
        PermissionCodes.FEES_SUBMIT_PAYMENT,
        PermissionCodes.STUDENTS_VIEW_OWN,
        PermissionCodes.NOTICES_VIEW,
        PermissionCodes.FEEDBACK_SUBMIT,
        PermissionCodes.SUBJECTS_VIEW,
    ],
    RoleNames.ACCOUNTS: [
        PermissionCodes.FEES_VIEW_ALL,
        PermissionCodes.FEES_VERIFY_PAYMENT,
        PermissionCodes.FEES_MANAGE,
        PermissionCodes.STUDENTS_VIEW_ALL,
        PermissionCodes.NOTICES_VIEW,
    ],
    RoleNames.FINANCE: [
        PermissionCodes.FEES_VIEW_ALL,
        PermissionCodes.FEES_MANAGE,
        PermissionCodes.NOTICES_VIEW,
    ],
    RoleNames.RECEPTIONIST: [
        PermissionCodes.STUDENTS_VIEW_ALL,
        PermissionCodes.NOTICES_VIEW,
        PermissionCodes.NOTICES_MANAGE,
        PermissionCodes.SUBJECTS_VIEW,
    ],
}