"""
Seed RBAC: roles + the academics permission catalog, then grant permissions
to roles. Idempotent — safe to run repeatedly.

    python manage.py seed_rbac
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Permission, Role, RolePermission
from apps.core.enums import UserRole

# --- permission catalog -----------------------------------------------------
PERMISSIONS = [
    # academic year
    ("view_academic_year", "View Academic Year"),
    ("create_academic_year", "Create Academic Year"),
    ("update_academic_year", "Update Academic Year"),
    ("delete_academic_year", "Delete Academic Year"),
    # program
    ("view_program", "View Program"),
    ("create_program", "Create Program"),
    ("update_program", "Update Program"),
    ("delete_program", "Delete Program"),
    # semester
    ("view_semester", "View Semester"),
    ("create_semester", "Create Semester"),
    ("update_semester", "Update Semester"),
    ("delete_semester", "Delete Semester"),
    # subject
    ("view_subject", "View Subject"),
    ("create_subject", "Create Subject"),
    ("update_subject", "Update Subject"),
    ("delete_subject", "Delete Subject"),
    # section
    ("view_section", "View Section"),
    ("manage_section", "Manage Section"),
    # curriculum
    ("view_curriculum", "View Curriculum"),
    ("manage_curriculum", "Manage Curriculum"),
    # students
    ("admit_student", "Admit Student"),
    ("view_student", "View Student"),
    ("update_student", "Update Student"),
    ("promote_student", "Promote Student"),
    ("manage_enrollment", "Manage Enrollment"),
    # faculty
    ("view_faculty", "View Faculty"),
    ("manage_faculty", "Manage Faculty"),
    ("assign_subject", "Assign Subject"),
    # attendance
    ("view_attendance", "View Attendance"),
    ("mark_attendance", "Mark Attendance"),
    ("manage_attendance", "Manage Attendance"),
    # routine
    ("view_routine", "View Routine"),
    ("manage_routine", "Manage Routine"),
    # faculty leave
    ("view_leave", "View Faculty Leave"),
    ("manage_leave", "Manage Faculty Leave"),
    # academic leave
    ("view_academic_leave", "View Academic Leave"),
    ("manage_academic_leave", "Manage Academic Leave"),
    # student self-service
    ("view_own_profile", "View Own Profile"),
    ("view_own_attendance", "View Own Attendance"),
    ("view_own_teachers", "View Own Teachers"),
    ("view_teacher_leave", "View Teacher Leave"),
    ("view_own_academic_leave", "View Own Academic Leave"),
    # exams / results
    ("view_exam", "View Exam"),
    ("manage_exam", "Manage Exam"),
    ("view_exam_schedule", "View Exam Schedule"),
    ("manage_exam_schedule", "Manage Exam Schedule"),
    ("enter_marks", "Enter Marks"),
    ("view_marks", "View Marks"),
    ("generate_result", "Generate Result"),
    ("publish_result", "Publish Result"),
    ("view_result", "View Result"),
    # fees / finance
    ("view_fee_structure", "View Fee Structure"),
    ("manage_fee_structure", "Manage Fee Structure"),
    ("view_student_fee", "View Student Fee"),
    ("generate_student_fee", "Generate Student Fee"),
    ("apply_scholarship", "Apply Scholarship / Discount"),
    ("pay_fee", "Pay / Collect Fee"),
    ("refund_payment", "Refund Payment"),
    ("view_payment", "View Payment"),
    ("view_receipt", "View Receipt"),
    ("view_own_fee", "View Own Fee"),
]

# --- role -> permission grants ----------------------------------------------
# Student-only permissions (scoped to the logged-in student's own data).
STUDENT_CODES = [
    "view_own_profile",
    "view_own_attendance",
    "view_own_teachers",
    "view_teacher_leave",
    "view_own_academic_leave",  # scoped: own academic year + global holidays
    "view_routine",
    "view_curriculum",
    "view_exam",
    "view_result",
    "view_own_fee",   # own student fees
    "view_receipt",   # own receipts (ReceiptViewSet scopes students to their own)
]

# Accountant (finance) permissions — the sole cash handler: collect + refund + view.
# Fee-structure setup, fee generation, and scholarships are ADMIN duties.
ACCOUNTANT_CODES = [
    "view_student_fee",
    "pay_fee",
    "refund_payment",
    "view_payment",
    "view_receipt",
]

# Money-handling permissions are EXCLUSIVE to the ACCOUNTANT role (separation of
# duties). A plain ADMIN can configure fees but cannot move money. A SUPER_ADMIN
# (superuser) bypasses RBAC entirely.
_MONEY_HANDLING = {"pay_fee", "refund_payment"}

# Codes staff roles like TEACHER must NOT receive via the blanket "view_*" grant.
_STUDENT_ONLY = {
    "view_own_profile", "view_own_attendance", "view_own_teachers",
    "view_teacher_leave", "view_own_academic_leave", "view_own_fee",
}
_FINANCE_VIEW = {
    "view_fee_structure", "view_student_fee", "view_payment", "view_receipt",
}

# ADMIN / SUPER_ADMIN get everything; TEACHER gets read-only + teaching actions
# (but NOT the student "own" or finance permissions).
VIEW_CODES = [
    c for c, _ in PERMISSIONS
    if c.startswith("view_") and c not in _STUDENT_ONLY and c not in _FINANCE_VIEW
]
TEACHER_CODES = VIEW_CODES + ["mark_attendance", "enter_marks"]

# ADMIN gets everything except the accountant-exclusive money-handling codes.
ADMIN_CODES = [c for c, _ in PERMISSIONS if c not in _MONEY_HANDLING]

ROLE_GRANTS = {
    UserRole.SUPER_ADMIN: "ALL",
    UserRole.ADMIN: ADMIN_CODES,
    UserRole.TEACHER: TEACHER_CODES,
    UserRole.ACCOUNTANT: ACCOUNTANT_CODES,
    UserRole.STUDENT: STUDENT_CODES,
}


class Command(BaseCommand):
    help = "Seed roles, permissions, and role-permission grants."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) roles
        roles = {}
        for value, label in UserRole.choices:
            role, created = Role.all_objects.get_or_create(
                name=value, defaults={"description": label}
            )
            if role.is_deleted:
                role.restore()
            roles[value] = role
            self.stdout.write(f"role {'created' if created else 'ok'}: {value}")

        # 2) permissions
        perms = {}
        for code, name in PERMISSIONS:
            perm, created = Permission.all_objects.get_or_create(
                code=code, defaults={"name": name}
            )
            if perm.is_deleted:
                perm.restore()
            perms[code] = perm
        self.stdout.write(f"permissions ensured: {len(perms)}")

        # 3) grants (authoritative: add target grants, prune the rest)
        grant_count = 0
        pruned_count = 0
        for role_name, codes in ROLE_GRANTS.items():
            role = roles[role_name]
            target = list(perms) if codes == "ALL" else codes
            for code in target:
                link, created = RolePermission.all_objects.get_or_create(
                    role=role, permission=perms[code]
                )
                if link.is_deleted:
                    link.restore()
                grant_count += 1
            # Revoke any active grant for this role that is no longer in target.
            stale = RolePermission.objects.filter(role=role).exclude(
                permission__code__in=set(target)
            )
            pruned_count += stale.count()
            stale.delete()  # soft delete
            self.stdout.write(f"{role_name}: {len(target)} permissions")

        self.stdout.write(self.style.SUCCESS(
            f"RBAC seeded ({grant_count} grants, {pruned_count} revoked)."
        ))