"""
Core services. The single choke point for writing audit/event records.

Call log_audit() from inside the service that performs the action, within the
same transaction, so the audit row is consistent with the change (rolls back
together). This is also the future hook for an event bus / outbox.
"""

from apps.core.audit import AuditLog


def log_audit(
    *,
    action,
    actor=None,
    instance=None,
    model_name: str = "",
    object_id=None,
    object_repr: str = "",
    changes: dict | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Record an audit event.

    Pass `instance` to auto-fill model_name/object_id/object_repr, or pass them
    explicitly for non-model events.
    """
    if instance is not None:
        model_name = model_name or instance._meta.label
        object_id = object_id if object_id is not None else str(instance.pk)
        object_repr = object_repr or str(instance)[:255]

    return AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=str(action),
        model_name=model_name,
        object_id=str(object_id) if object_id is not None else None,
        object_repr=object_repr[:255],
        changes=changes or {},
        metadata=metadata or {},
        ip_address=ip_address,
    )
