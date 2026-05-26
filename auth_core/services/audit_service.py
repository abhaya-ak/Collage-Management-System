# auth_core/services/audit_service.py
import logging

from auth_core.models import AuditLog
from auth_core.utils import get_client_ip

logger = logging.getLogger('auth_core.audit')


class AuditService:
    """
    Fire-and-forget security event logger.

    CRITICAL DESIGN RULE: this class NEVER raises exceptions.
    An audit failure must NEVER crash an auth request.
    All exceptions are caught, logged to the Python logger, then suppressed.
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
                ip_address = get_client_ip(request),
                user_agent = (request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''),
                metadata   = metadata or {},
            )
        except Exception:
            # Audit failure is non-fatal — auth must not crash because logging failed.
            # Log to the Python logger so the failure is visible in server logs
            # without surfacing it to the client.
            logger.exception(
                'AuditService.log() failed silently — event=%s user_id=%s',
                event,
                getattr(user, 'pk', None),
            )
