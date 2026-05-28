# auth_core/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

# ─────────────────────────────────────────────────────────────────────────────
# 1. UserProfile  — extends the thin User(AbstractUser):pass with real data
# ─────────────────────────────────────────────────────────────────────────────
class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    avatar     = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone      = models.CharField(max_length=20, blank=True)
    bio        = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"


# ─────────────────────────────────────────────────────────────────────────────
# 2. UserSession  — server-side session record; makes real logout possible
# ─────────────────────────────────────────────────────────────────────────────
class UserSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    # jti = JWT ID claim from the REFRESH token that opened this session
    jti          = models.CharField(max_length=255, unique=True, db_index=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    closed_at    = models.DateTimeField(null=True, blank=True)
    is_active    = models.BooleanField(default=True, db_index=True)
    access_jti   = models.CharField(max_length=255, db_index=True, blank=True, default='')  # ← ADD THIS

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session({self.user.username}, jti={self.jti[:8]}…, active={self.is_active})"


# ─────────────────────────────────────────────────────────────────────────────
# 3. TokenBlacklist  — blacklisted JTIs; checked by AuthMiddleware on every req
# ─────────────────────────────────────────────────────────────────────────────
class TokenBlacklist(models.Model):
    # jti of the REFRESH token that was revoked
    jti            = models.CharField(max_length=255, unique=True, db_index=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    # expires_at lets a cron job delete stale rows safely
    expires_at     = models.DateTimeField()

    class Meta:
        ordering = ['-blacklisted_at']

    def __str__(self):
        return f"Blacklisted(jti={self.jti[:8]}…)"


# ─────────────────────────────────────────────────────────────────────────────
# 4. AuditLog  — immutable security event log
#    on_delete=SET_NULL so deleting a user doesn't erase the audit trail
# ─────────────────────────────────────────────────────────────────────────────
class AuditLog(models.Model):
    class Event(models.TextChoices):
        REGISTER               = 'register',               'User Registered'
        LOGIN                  = 'login',                  'Login Success'
        LOGIN_FAILED           = 'login_failed',           'Login Failed'
        LOGOUT                 = 'logout',                 'Logout'
        TOKEN_REFRESH          = 'token_refresh',          'Token Refreshed'
        PASSWORD_CHANGE        = 'password_change',        'Password Changed'
        TOKEN_BLACKLISTED      = 'token_blacklisted',      'Token Blacklisted'
        PASSWORD_RESET_REQUEST = 'password_reset_request', 'Password Reset Requested'
        PASSWORD_RESET_CONFIRM = 'password_reset_confirm', 'Password Reset Confirmed'

    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    event      = models.CharField(max_length=30, choices=Event.choices, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    # Flexible metadata — e.g. {'username_attempted': 'admin'} for LOGIN_FAILED
    metadata   = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Audit({self.event}, user={self.user_id}, {self.created_at})"


# ─────────────────────────────────────────────────────────────────────────────
# 5. PasswordResetToken  — single-use, time-limited reset credential
# ─────────────────────────────────────────────────────────────────────────────
class PasswordResetToken(models.Model):
    """
    One row per pending reset request.
    Consumed (used_at set) after a successful password change.
    Expired rows are safe to delete by a cron job (expires_at < now, used_at IS NULL).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    # UUID4 hex — 128 bits of entropy, URL-safe
    token      = models.CharField(max_length=64, unique=True, db_index=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()          # set by PasswordResetService.request_reset()
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_valid(self) -> bool:
        """True iff the token has not been used and has not yet expired."""
        return self.used_at is None and timezone.now() < self.expires_at

    def __str__(self):
        return f"ResetToken(user={self.user_id}, valid={self.is_valid})"