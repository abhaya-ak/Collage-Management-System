# auth_core/services/session_service.py
from django.utils import timezone

from auth_core.models import UserSession, TokenBlacklist


def _get_client_ip(request) -> str | None:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR') if request else None
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') if request else None


class SessionService:
    """
    Manages server-side session records (UserSession).
    This is what makes logout REAL — without a server-side session,
    a stolen token is valid until its expiry timestamp.
    """

    @staticmethod
    def create(user, jti: str, request=None) -> UserSession:
        """Opens a new session when a user logs in or refreshes tokens."""
        return UserSession.objects.create(
            user       = user,
            jti        = jti,
            ip_address = _get_client_ip(request),
            user_agent = (request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''),
        )

    @staticmethod
    def validate(jti: str) -> bool:
        """
        Returns True only if:
          1. The jti is NOT in TokenBlacklist, AND
          2. There is an active UserSession with this jti.
        This is the core logout enforcement check.
        """
        if TokenBlacklist.objects.filter(jti=jti).exists():
            return False
        return UserSession.objects.filter(jti=jti, is_active=True).exists()

    @staticmethod
    def close(jti: str) -> None:
        """Closes session on logout or token rotation."""
        UserSession.objects.filter(jti=jti, is_active=True).update(
            is_active = False,
            closed_at = timezone.now(),
        )

    @staticmethod
    def touch(jti: str) -> None:
        """
        Updates last_seen_at. Called by AuthMiddleware on authenticated
        requests to track activity without a full DB write on every hit.
        Uses update() to avoid triggering auto_now on other fields.
        """
        UserSession.objects.filter(jti=jti).update(last_seen_at=timezone.now())

    @staticmethod
    def close_all_for_user(user) -> int:
        """Force-closes ALL active sessions for a user (admin action / password reset)."""
        updated = UserSession.objects.filter(user=user, is_active=True).update(
            is_active = False,
            closed_at = timezone.now(),
        )
        return updated
