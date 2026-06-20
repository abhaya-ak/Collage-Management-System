"""
AuditLog — immutable record of WHO did WHAT to WHICH object, WHEN.

Inherits BaseModel (UUID + timestamps) but intentionally NOT SoftDeleteMixin:
audit history must never be deletable.

The `action` field stores a semantic event name (see AuditEvent), so this table
also serves as the foundation for an event log. Target is referenced by string
(model_name + object_id) to stay PK-type-agnostic and free of contenttypes.

Write rows via apps.core.services.log_audit(), never by hand.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class AuditLog(BaseModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100, db_index=True)

    # Target (generic, string-based).
    model_name = models.CharField(max_length=120, blank=True, db_index=True)
    object_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True, default="")

    # Detail payloads.
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["actor", "action"]),
        ]

    def __str__(self):
        who = self.actor_id or "system"
        return f"[{self.action}] {self.model_name}({self.object_id}) by {who}"
