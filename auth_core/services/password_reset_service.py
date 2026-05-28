# auth_core/services/password_reset_service.py
"""
Password reset flow — two-step:

  Step 1: POST /api/v1/auth/forgot-password/
          PasswordResetService.request_reset(email)
          → creates PasswordResetToken, sends email (no-op if email unknown)

  Step 2: POST /api/v1/auth/reset-password/
          PasswordResetService.confirm_reset(token, new_password)
          → validates token, sets password, revokes all sessions

Design decisions
────────────────
• request_reset() is silent for unknown emails — prevents user-enumeration.
• Token is UUID4 (128-bit entropy) stored as a hex string.
• Only ONE valid (unused + unexpired) token per user at a time. Any previous
  unused tokens for the user are deleted before creating a new one.
• Expiry is 1 hour. Configurable via RESET_TOKEN_EXPIRY_MINUTES env var.
• confirm_reset() calls SessionService.close_all_for_user() — a successful
  reset immediately invalidates every active session (stolen refresh tokens
  with up to 7-day lifetime are neutralised).
• Email is sent OUTSIDE the DB transaction — a transient SMTP failure must
  not roll back the created token. The user can request a new one.
"""
import uuid
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from auth_core.models import AuditLog, PasswordResetToken
from auth_core.services.audit_service import AuditService
from auth_core.services.session_service import SessionService

logger = logging.getLogger('auth_core.password_reset')
User = get_user_model()

# How long a reset link is valid (override with RESET_TOKEN_EXPIRY_MINUTES env var)
_EXPIRY_MINUTES = int(getattr(settings, 'RESET_TOKEN_EXPIRY_MINUTES', 60))


class PasswordResetService:

    # ── Step 1: request ───────────────────────────────────────────────────────

    @staticmethod
    def request_reset(email: str, request=None) -> None:
        """
        Initiates a password reset for the account with the given email.

        Silently returns (no error) when the email is not registered — this
        prevents attackers from enumerating valid accounts via the API.

        Side-effects:
          • Deletes any existing unused PasswordResetToken rows for the user.
          • Creates a new PasswordResetToken (expires in _EXPIRY_MINUTES).
          • Sends one email with the reset link.
          • Fires a PASSWORD_RESET_REQUEST audit event.
        """
        try:
            user = User.objects.get(email__iexact=email.strip(), is_active=True)
        except User.DoesNotExist:
            # Silent — do NOT reveal whether the address is registered.
            return

        token_str = uuid.uuid4().hex  # 32-char lowercase hex, URL-safe

        with transaction.atomic():
            # Invalidate any outstanding unused tokens for this user.
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).delete()

            reset_token = PasswordResetToken.objects.create(
                user       = user,
                token      = token_str,
                expires_at = timezone.now() + timedelta(minutes=_EXPIRY_MINUTES),
            )

        # Email is sent OUTSIDE the transaction: a transient SMTP failure must
        # not roll back the DB write.  The user can re-request if email fails.
        PasswordResetService._send_reset_email(user, reset_token, request)

        # Audit — fire-and-forget, never raises
        AuditService.log(
            event    = AuditLog.Event.PASSWORD_RESET_REQUEST,
            user     = user,
            request  = request,
            metadata = {'email': email},
        )

    # ── Step 2: confirm ───────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def confirm_reset(token_str: str, new_password: str, request=None) -> None:
        """
        Validates the reset token and sets the new password.

        Raises ValueError for:
          • Unknown / already-used token
          • Expired token
          • Password failing Django's AUTH_PASSWORD_VALIDATORS

        On success:
          • Marks the token as used (idempotency — cannot be replayed).
          • Sets the new password.
          • Revokes ALL active sessions (neutralises stolen refresh tokens).
          • Fires a PASSWORD_RESET_CONFIRM audit event (outside the tx).
        """
        try:
            reset_token = (
                PasswordResetToken.objects
                .select_related('user')
                .select_for_update()           # row-level lock prevents replays
                .get(token=token_str, used_at__isnull=True)
            )
        except PasswordResetToken.DoesNotExist:
            raise ValueError('This reset link is invalid or has already been used.')

        if not reset_token.is_valid:
            raise ValueError(
                'This reset link has expired. Please request a new one.'
            )

        # Validate new password against Django's password validators
        try:
            validate_password(new_password, user=reset_token.user)
        except DjangoValidationError as exc:
            raise ValueError(' '.join(exc.messages))

        user = reset_token.user

        # Mark consumed first — prevents a race-condition replay even without the lock
        reset_token.used_at = timezone.now()
        reset_token.save(update_fields=['used_at'])

        # Set the new password
        user.set_password(new_password)
        user.save(update_fields=['password', 'last_login'])

        # Revoke every active session — stolen refresh tokens (7-day lifetime)
        # are neutralised immediately.
        SessionService.close_all_for_user(user)

        # Audit outside transaction — non-fatal
        AuditService.log(
            event    = AuditLog.Event.PASSWORD_RESET_CONFIRM,
            user     = user,
            request  = request,
            metadata = {'token_prefix': token_str[:8]},
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _send_reset_email(user, reset_token: PasswordResetToken, request=None) -> None:
        """
        Constructs and sends the password-reset email.

        The reset URL is built from FRONTEND_URL in settings (env var).
        In development (EMAIL_BACKEND = console), the link is printed to stdout.
        """
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        reset_url    = f'{frontend_url}/reset-password?token={reset_token.token}'
        expiry_mins  = _EXPIRY_MINUTES

        subject = 'Reset your CMS password'
        message = (
            f'Hi {user.first_name or user.username},\n\n'
            f'We received a request to reset the password for your account.\n\n'
            f'Click the link below to set a new password (valid for {expiry_mins} minutes):\n\n'
            f'{reset_url}\n\n'
            f'If you did not request a password reset, you can safely ignore this email.\n\n'
            f'— The CMS Team'
        )

        try:
            send_mail(
                subject             = subject,
                message             = message,
                from_email          = settings.DEFAULT_FROM_EMAIL,
                recipient_list      = [user.email],
                fail_silently       = False,
            )
        except Exception:
            # Email failure is logged but never propagated — the token was already
            # created; the user can request another reset if this one silently failed.
            logger.exception(
                'PasswordResetService: failed to send email to user_id=%s', user.pk
            )
