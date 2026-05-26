# auth_core/services/session_service.py
from django.db import transaction as db_transaction
from django.utils import timezone

from auth_core.models import UserSession
from auth_core.utils import get_client_ip

# Must match the key format used in middleware.py
_SESSION_CACHE_KEY = 'auth:session:{jti}'


def _invalidate_cache(*access_jtis):
    """
    Deletes session cache entries for the given access_jtis.
    Called via transaction.on_commit() so cache is only cleared
    after the DB write is committed — if the transaction rolls back,
    the cache entry remains valid (correct behavior).
    """
    from django.core.cache import cache
    keys = [_SESSION_CACHE_KEY.format(jti=j) for j in access_jtis if j]
    if keys:
        cache.delete_many(keys)


class SessionService:
    """
    Manages server-side session records (UserSession).

    jti column mapping:
        UserSession.jti        → refresh token jti  (session anchor)
        UserSession.access_jti → access token jti   (middleware cache key)
    """

    @staticmethod
    def create(user, jti: str, request=None, access_jti: str = '') -> UserSession:
        """Opens a new session when a user logs in or refreshes tokens."""
        return UserSession.objects.create(
            user       = user,
            jti        = jti,
            ip_address = get_client_ip(request),
            access_jti = access_jti,
            user_agent = (request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''),
        )

    @staticmethod
    def validate_by_access_jti(access_jti: str) -> bool:
        """Positive assertion — active session with this access_jti must exist."""
        return UserSession.objects.filter(
            access_jti=access_jti,
            is_active=True,
        ).exists()

    @staticmethod
    def validate_by_refresh_jti(jti: str) -> bool:
        """
        Checks session is active by refresh jti — used only for pre-flight
        checks outside a transaction. For the actual rotation use
        lock_for_rotation() inside transaction.atomic() instead.
        """
        return UserSession.objects.filter(
            jti=jti,
            is_active=True,
        ).exists()

    @staticmethod
    def lock_for_rotation(jti: str) -> UserSession:
        """
        Issues SELECT FOR UPDATE on the session row keyed by refresh jti.
        Must be called INSIDE transaction.atomic().

        This serializes concurrent refresh requests for the same token —
        the second request blocks until the first commits, then sees
        is_active=False and raises DoesNotExist → 401.

        Raises UserSession.DoesNotExist if the session is not active.
        """
        return UserSession.objects.select_for_update().get(
            jti=jti,
            is_active=True,
        )

    @staticmethod
    def close(jti: str) -> None:
        """
        Closes a session on logout or token rotation. Keyed by refresh jti.
        Schedules cache invalidation via on_commit so the cache entry is only
        cleared after the DB write commits — rollback leaves cache intact.
        """
        # Fetch access_jti before update so we can invalidate its cache entry
        access_jti = (
            UserSession.objects
            .filter(jti=jti, is_active=True)
            .values_list('access_jti', flat=True)
            .first()
        )
        UserSession.objects.filter(jti=jti, is_active=True).update(
            is_active = False,
            closed_at = timezone.now(),
        )
        if access_jti:
            db_transaction.on_commit(lambda: _invalidate_cache(access_jti))

    @staticmethod
    def touch(access_jti: str) -> None:
        """
        Updates last_seen_at for activity tracking.
        Keyed on access_jti column (fix: was incorrectly querying refresh jti).
        """
        UserSession.objects.filter(access_jti=access_jti, is_active=True).update(
            last_seen_at=timezone.now(),
        )

    @staticmethod
    def close_all_for_user(user) -> int:
        """
        Force-closes ALL active sessions for a user (password change / admin).
        Schedules cache invalidation for all closed sessions via on_commit.
        """
        qs = UserSession.objects.filter(user=user, is_active=True)
        access_jtis = list(qs.values_list('access_jti', flat=True))
        updated = qs.update(is_active=False, closed_at=timezone.now())
        if access_jtis:
            db_transaction.on_commit(lambda: _invalidate_cache(*access_jtis))
        return updated
