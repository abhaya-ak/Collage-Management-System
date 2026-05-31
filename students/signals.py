# students/signals.py
#
# Listens for UserRole saves and ensures the correct domain profile
# exists for the assigned role.
#
# TEACHER → creates Teacher(department='Unassigned') if none exists.
#            Admin must PATCH /api/v1/students/teachers/{id}/ to set the real dept.
#
# STUDENT → cannot auto-create because Student.roll_no is unique and has no
#            default. Admin must POST /api/v1/students/profiles/ with full data.
#            A clear NotFound is raised in views when profile is missing.
#
# ADMIN / SUPER_ADMIN → no domain profile model required. RBAC permissions
#            already grant the necessary access.

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import UserRole
from users.constants import RoleNames

logger = logging.getLogger(__name__)


@receiver(post_save, sender=UserRole)
def sync_domain_profile_on_role_save(sender, instance, created, **kwargs):
    """
    Fires after every UserRole INSERT or UPDATE.

    On role=teacher  → ensures a Teacher row exists (idempotent via get_or_create).
    On role change   → also fires, so switching TO teacher creates the profile.
    """
    from students.models import Teacher     # local import avoids circular imports

    role_name = instance.role.name
    user      = instance.user

    if role_name == RoleNames.TEACHER:
        teacher, was_created = Teacher.objects.get_or_create(
            user=user,
            defaults={'department': 'Unassigned'},
        )
        if was_created:
            logger.info(
                'Signal: auto-created Teacher profile for user pk=%s (%s). '
                'Admin should update department via PATCH /api/v1/students/teachers/%s/',
                user.pk, user.username, teacher.pk,
            )
        return

    # If role changed AWAY from teacher, we intentionally leave the Teacher row
    # intact — deleting academic profile data on a role change is destructive.
    # Admin can explicitly delete via DELETE /api/v1/students/teachers/{id}/ if needed.
