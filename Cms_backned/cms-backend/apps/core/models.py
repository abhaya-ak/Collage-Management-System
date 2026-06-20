"""
Phase 1 — Base Infrastructure.

Step 1: BaseModel        -> UUID id + created_at + updated_at   (depends on: nothing)
Step 2: SoftDeleteMixin  -> is_deleted + deleted_at + soft delete (depends on: BaseModel)

Domain models combine both:

    from apps.core.models import BaseModel, SoftDeleteMixin

    class Student(BaseModel, SoftDeleteMixin):
        ...
        
"""

import uuid

from django.db import models
from django.utils import timezone

from apps.core.managers import ActiveManager, AllManager


class BaseModel(models.Model):
    """
    Step 1 — the root abstract model. Every model in the CMS inherits this.

    Provides:
        id          -> UUID primary key (non-editable)
        created_at  -> set once on creation
        updated_at  -> updated on every save
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SoftDeleteMixin(models.Model):
    """
    Step 2 — soft delete support. Marks rows as deleted instead of removing them,
    protecting critical CMS data (students, fees, attendance, results).

    Managers (Step 3):
        objects / active_objects -> non-deleted rows only
        all_objects              -> every row, including soft-deleted
    """

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    active_objects = ActiveManager()
    all_objects = AllManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, hard=False):
        """Soft delete by default. Pass hard=True to delete permanently."""
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return (1, {self._meta.label: 1})

    def restore(self):
        """Reverse a soft delete."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


# Import concrete models so Django's app registry discovers them.
# (AuditLog is defined in audit.py to keep this file focused on abstract bases.)
from apps.core.audit import AuditLog  # noqa: E402,F401
