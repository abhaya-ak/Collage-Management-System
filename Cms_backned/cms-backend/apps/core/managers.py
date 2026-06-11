"""
Step 3 — Custom Managers.

Purpose: hide soft-deleted records automatically.

Three managers are exposed on SoftDeleteMixin:
    objects         -> non-deleted rows only  (safe default)
    active_objects  -> non-deleted rows only  (explicit, readable name)
    all_objects     -> every row, including soft-deleted (escape hatch)

Depends on: the `is_deleted` field provided by SoftDeleteMixin.
"""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet aware of soft delete."""

    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def delete(self):
        """Bulk soft delete (overrides QuerySet.delete)."""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Permanent bulk delete."""
        return super().delete()


class ActiveManager(models.Manager):
    """Default manager — automatically excludes soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllManager(models.Manager):
    """Returns every row, including soft-deleted ones."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)
