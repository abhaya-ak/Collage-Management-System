# auth_core/services/lockout_service.py
"""
Brute-force lockout logic — completely isolated from AuthService so it can
be tested independently and swapped out (e.g. for a Redis-backed version).

Policy (driven by LoginAttempt model constants):
  - MAX_ATTEMPTS    = 5   consecutive failures  → lock
  - LOCKOUT_MINUTES = 15  minutes lock duration
  - Tracker is per (username, ip_address) pair
"""
from django.utils import timezone
from datetime import timedelta

from auth_core.models import LoginAttempt


class LockoutService:

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def check_lockout(username: str, ip_address: str | None) -> None:
        """
        Raise PermissionDenied if this (username, ip) pair is currently locked.

        Call this BEFORE authenticate() so a locked account never even hits
        Django's password-hash comparison (timing-safe by design).

        Raises:
            PermissionDenied — with seconds_remaining embedded in detail so
                               the API response can surface a Retry-After hint.
        """
        from rest_framework.exceptions import PermissionDenied

        attempt = LockoutService._get(username, ip_address)
        if attempt is None:
            return  # no history → definitely not locked

        if attempt.is_locked:
            secs = attempt.seconds_remaining
            raise PermissionDenied(
                f"Account locked due to too many failed login attempts. "
                f"Try again in {secs} seconds."
            )

    @staticmethod
    def record_failure(username: str, ip_address: str | None) -> LoginAttempt:
        """
        Increment the failure counter for (username, ip).
        If the counter hits MAX_ATTEMPTS, set locked_until = now + LOCKOUT_MINUTES.

        Uses update_or_create to avoid race conditions between concurrent
        wrong-password requests for the same account.

        Returns the updated LoginAttempt row.
        """
        attempt, _ = LoginAttempt.objects.get_or_create(
            username   = username,
            ip_address = ip_address,
            defaults   = {'failed_count': 0},
        )

        # If a previous lockout has expired, reset the counter first so the
        # window starts fresh rather than immediately re-locking.
        if attempt.locked_until is not None and not attempt.is_locked:
            attempt.failed_count = 0
            attempt.locked_until = None

        attempt.failed_count += 1

        if attempt.failed_count >= LoginAttempt.MAX_ATTEMPTS:
            attempt.locked_until = timezone.now() + timedelta(
                minutes=LoginAttempt.LOCKOUT_MINUTES
            )

        attempt.save(update_fields=['failed_count', 'locked_until', 'last_attempt'])
        return attempt

    @staticmethod
    def clear(username: str, ip_address: str | None) -> None:
        """
        Remove the tracker row after a successful login.

        Deleting (rather than zeroing) keeps the table lean and ensures a
        brand-new window on the next failure run.
        """
        LoginAttempt.objects.filter(
            username   = username,
            ip_address = ip_address,
        ).delete()

    # ── Internal helper ───────────────────────────────────────────────────────

    @staticmethod
    def _get(username: str, ip_address: str | None) -> LoginAttempt | None:
        try:
            return LoginAttempt.objects.get(username=username, ip_address=ip_address)
        except LoginAttempt.DoesNotExist:
            return None
