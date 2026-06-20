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
]

# --- role -> permission grants ----------------------------------------------
# ADMIN / SUPER_ADMIN get everything; TEACHER gets read-only + teaching actions.
VIEW_CODES = [c for c, _ in PERMISSIONS if c.startswith("view_")]
TEACHER_CODES = VIEW_CODES + ["mark_attendance"]

ROLE_GRANTS = {
    UserRole.SUPER_ADMIN: "ALL",
    UserRole.ADMIN: "ALL",
    UserRole.TEACHER: TEACHER_CODES,
    UserRole.ACCOUNTANT: [],
    UserRole.STUDENT: [],
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

        # 3) grants
        grant_count = 0
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
            self.stdout.write(f"{role_name}: {len(target)} permissions")

        self.stdout.write(self.style.SUCCESS(f"RBAC seeded ({grant_count} grants)."))