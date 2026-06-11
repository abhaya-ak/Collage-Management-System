"""
Sprint 4 — Step 2: Account services (business logic layer).

Views stay thin and call these:
    authenticate_user, change_password, assign_role, remove_role, get_user_permissions
"""

from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.accounts.models import CustomUser, Role, UserRole
from apps.core.enums import AuditEvent
from apps.core.exceptions import PermissionDeniedException, ValidationException
from apps.core.services import log_audit


def authenticate_user(email: str, password: str) -> CustomUser:
    """Verify credentials and return the active user, or raise."""
    email = (email or "").strip().lower()
    # `objects` already excludes soft-deleted users.
    user = CustomUser.objects.filter(email__iexact=email).first()

    # Run check_password even when user is missing to reduce timing leaks.
    if user is None or not user.check_password(password):
        raise ValidationException("Invalid email or password.")
    if not user.is_active:
        raise PermissionDeniedException("This account is disabled.")

    update_last_login(None, user)
    return user


@transaction.atomic
def change_password(user: CustomUser, old_password: str, new_password: str) -> CustomUser:
    """Change a user's password after verifying the old one."""
    if not user.check_password(old_password):
        raise ValidationException("Current password is incorrect.")
    try:
        validate_password(new_password, user)
    except DjangoValidationError as exc:
        raise ValidationException(list(exc.messages))
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    return user


@transaction.atomic
def assign_role(user: CustomUser, role_name: str) -> UserRole:
    """Assign a role to a user (idempotent; restores a soft-deleted link)."""
    role = Role.objects.filter(name=role_name).first()
    if role is None:
        raise ValidationException(f"Role '{role_name}' does not exist.")

    link, _ = UserRole.all_objects.get_or_create(user=user, role=role)
    if link.is_deleted:
        link.restore()
    return link


@transaction.atomic
def remove_role(user: CustomUser, role_name: str) -> None:
    """Remove a role from a user (soft delete the link)."""
    role = Role.objects.filter(name=role_name).first()
    if role is None:
        raise ValidationException(f"Role '{role_name}' does not exist.")
    UserRole.objects.filter(user=user, role=role).delete()  # soft delete


def get_user_permissions(user: CustomUser) -> list[str]:
    """Resolve all permission codes granted to a user through their roles."""
    return sorted(user.get_permission_codes())


@transaction.atomic
def create_user_with_roles(*, email, password, roles, first_name="", last_name="",
                           phone_number="", actor=None) -> CustomUser:
    """Superuser creates a user account and assigns roles in one transaction."""
    user = CustomUser.objects.create_user(
        email=email, password=password,
        first_name=first_name, last_name=last_name, phone_number=phone_number,
    )
    for role_name in roles:
        assign_role(user, role_name)
    log_audit(
        action=AuditEvent.CREATE, actor=actor, instance=user,
        metadata={"roles": list(roles)},
    )
    return user


@transaction.atomic
def set_roles(user: CustomUser, roles: list, actor=None) -> CustomUser:
    """Replace a user's roles with the given list (soft-removes the rest)."""
    current = user.get_role_names()
    target = set(roles)
    for role_name in target - current:
        assign_role(user, role_name)
    for role_name in current - target:
        remove_role(user, role_name)
    log_audit(
        action=AuditEvent.UPDATE, actor=actor, instance=user,
        changes={"roles": {"from": sorted(current), "to": sorted(target)}},
    )
    return user


@transaction.atomic
def update_profile(user: CustomUser, data: dict) -> CustomUser:
    """
    Self-service profile update. Only first_name, last_name, phone_number,
    profile_photo may change here. Tracks changed fields and audits.
    """
    editable = ["first_name", "last_name", "phone_number", "profile_photo", "username"]
    changed = []
    for field in editable:
        if field in data and getattr(user, field) != data[field]:
            setattr(user, field, data[field])
            changed.append(field)

    if changed:
        user.save(update_fields=changed + ["updated_at"])
        log_audit(
            action=AuditEvent.PROFILE_UPDATED,
            actor=user,            # self-service: actor == target
            instance=user,
            changes={"changed_fields": changed},
        )
    return user