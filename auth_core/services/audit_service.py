# auth_core/services/audit_service.py
from auth_core.models import AuditLog


def _get_client_ip(request) -> str | None:
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AuditService:
    """
    Fire-and-forget security event logger.

    CRITICAL DESIGN RULE: this class NEVER raises exceptions.
    An audit failure must NEVER crash an auth request.
    Every method wraps its body in a bare except.
    """

    @staticmethod
    def log(
        event: str,
        user=None,
        request=None,
        metadata: dict | None = None,
    ) -> None:
        try:
            AuditLog.objects.create(
                user       = user,
                event      = event,
                ip_address = _get_client_ip(request),
                user_agent = (request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''),
                metadata   = metadata or {},
            )
        except Exception:
            # Intentionally swallowed — audit failure is non-fatal
            pass
