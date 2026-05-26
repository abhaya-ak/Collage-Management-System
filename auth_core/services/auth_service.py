# auth_core/services/auth_service.py
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed

from auth_core.models import AuditLog, UserProfile
from auth_core.services.jwt_service import JWTService
from auth_core.services.session_service import SessionService
from auth_core.services.audit_service import AuditService
from users.models import Role, UserRole
from users.constants import RoleNames

User = get_user_model()

class AuthService:
    """
    Orchestrates the full auth lifecycle.
    Views are thin — they validate serializer input then call here.
    All token, session, and audit operations go through this class.
    """

    # ── Register ─────────────────────────────────────────────────────────────

    @staticmethod
    def register(validated_data: dict, request=None) -> dict:
        """
        1. Create User + Profile + Role assignment
        2. Generate JWT tokens
        3. Create UserSession (refresh jti + access jti)
        4. Audit log REGISTER
        Returns: {'user': User, 'access': str, 'refresh': str, 'jti': str}

        ALL DB writes (steps 1-3) are wrapped in transaction.atomic().
        A crash mid-way rolls back completely — no orphan user record with
        missing session can exist.
        """
        with transaction.atomic():
            user = User.objects.create_user(
                username   = validated_data['username'],
                email      = validated_data.get('email', ''),
                password   = validated_data['password'],
                first_name = validated_data.get('first_name', ''),
                last_name  = validated_data.get('last_name', ''),
            )

            UserProfile.objects.create(user=user)

            # Default role: student
            # WHY get_or_create: if seed_roles was not yet run, this prevents a
            # hard crash. The role will exist but without permissions until seeded.
            # Run `python manage.py seed_roles` before accepting registrations.
            role, _ = Role.objects.get_or_create(name=RoleNames.STUDENT)
            UserRole.objects.create(user=user, role=role)

            tokens = JWTService.generate_tokens(user)
            SessionService.create(user, tokens['jti'], request, access_jti=tokens['access_jti'])

        # Audit is intentionally OUTSIDE the transaction.
        # A logging failure must never roll back a completed registration.
        AuditService.log(
            event    = AuditLog.Event.REGISTER,
            user     = user,
            request  = request,
            metadata = {'username': user.username},
        )

        return {'user': user, **tokens}

    # ── Login ─────────────────────────────────────────────────────────────────

    @staticmethod
    def login(username: str, password: str, request=None) -> dict:
        """
        1. authenticate() — Django's built-in credential check (outside tx — no writes)
        2. If fail: log LOGIN_FAILED (outside tx — must persist even on failure), raise 401
        3. If inactive: raise 401
        4. [ATOMIC] Generate tokens + create session
        5. Audit log LOGIN (outside tx — non-fatal)
        Returns: {'user': User, 'access': str, 'refresh': str, 'jti': str}

        authenticate() and LOGIN_FAILED audit are intentionally OUTSIDE the transaction:
        - authenticate() does no writes
        - LOGIN_FAILED must be recorded even when the request fails
        """
        # Step 1 — credential check (read-only, no transaction needed)
        user = authenticate(request=request, username=username, password=password)

        if user is None:
            # LOGIN_FAILED must persist independently — not rolled back with any tx
            AuditService.log(
                event    = AuditLog.Event.LOGIN_FAILED,
                request  = request,
                metadata = {'username_attempted': username},
            )
            raise AuthenticationFailed('Invalid username or password.')

        if not user.is_active:
            raise AuthenticationFailed('This account has been deactivated.')

        # Step 2 — atomic token issuance + session creation
        # If SessionService.create() fails (e.g. DB constraint), the generated
        # tokens are never returned — no orphan tokens with missing sessions.
        with transaction.atomic():
            tokens = JWTService.generate_tokens(user)
            SessionService.create(user, tokens['jti'], request, access_jti=tokens['access_jti'])

        # Audit is intentionally OUTSIDE the transaction.
        # A logging failure must never roll back a completed login.
        AuditService.log(
            event    = AuditLog.Event.LOGIN,
            user     = user,
            request  = request,
            metadata = {'username': user.username},
        )

        return {'user': user, **tokens}

    # ── Logout ────────────────────────────────────────────────────────────────

    @staticmethod
    def logout(refresh_token: str, request=None, user=None) -> None:
        """
        1. Parse the refresh token — silently absorb invalid/expired tokens
        2. Ownership check — reject tokens that belong to a different user
           (prevents user A from logging out user B by submitting B's token)
        3. Blacklist the jti + close the UserSession
        4. Log LOGOUT

        Does NOT raise on any failure — logout is always idempotent from the
        UX perspective. Errors are swallowed, not surfaced.
        """
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        # Step 1 — parse the raw token string
        try:
            parsed = RefreshToken(refresh_token)
        except TokenError:
            # Expired, malformed, or tampered — nothing to revoke
            return

        # Step 2 — ownership check
        # The token's user_id claim MUST match the currently authenticated user.
        # If they don't match, user A is trying to blacklist user B's token.
        # We return silently (no error) to avoid leaking token validity info.
        if user is not None and str(parsed.get('user_id')) != str(user.pk):
            return

        # Step 3 — atomic: blacklist token + close session together.
        # If SessionService.close() fails after blacklist_refresh_token() writes,
        # the full rollback means the token is NOT blacklisted and the session
        # stays open — user can retry logout cleanly. Without this, a crash
        # between the two writes leaves a zombie session (is_active=True)
        # whose token is already blacklisted — an inconsistent state.
        jti = None  # safe default — guards the audit block below if tx raises
        with transaction.atomic():
            jti = JWTService.blacklist_refresh_token(refresh_token)
            if jti:
                SessionService.close(jti)

        # Audit is intentionally OUTSIDE the transaction.
        # A logging failure must never roll back a completed logout.
        if jti:
            AuditService.log(
                event    = AuditLog.Event.LOGOUT,
                user     = user,
                request  = request,
                metadata = {'jti_prefix': jti[:8]},
            )




    # ── Refresh ───────────────────────────────────────────────────────────────

    @staticmethod
    def refresh(refresh_token: str, request=None) -> dict:
        """
        Secure token rotation:
        1. Parse refresh token — raise if malformed
        2. Check TokenBlacklist — raise if revoked
        3. Check UserSession.is_active — raise if session closed
        4. Blacklist OLD refresh token + close OLD session
        5. Generate NEW token pair + open NEW session
        6. Log TOKEN_REFRESH
        Returns: {'access': str, 'refresh': str, 'jti': str}
        """
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError
        from auth_core.models import TokenBlacklist

        try:
            refresh = RefreshToken(refresh_token)
        except TokenError as exc:
            raise AuthenticationFailed(f'Invalid refresh token: {exc}')

        jti = str(refresh['jti'])

        if TokenBlacklist.objects.filter(jti=jti).exists():
            raise AuthenticationFailed('Refresh token has been revoked. Please log in again.')

        try:
            user = User.objects.get(pk=refresh['user_id'])
        except User.DoesNotExist:
            raise AuthenticationFailed('User account not found.')

        # ── Atomic rotation with row-level lock (Issue 5 — race condition fix) ─
        # lock_for_rotation() issues SELECT FOR UPDATE on the session row.
        # Concurrent refresh requests for the same token block here until
        # the first request commits. The second then finds is_active=False
        # and raises DoesNotExist → 401. Duplicate sessions are impossible.
        #
        # This also replaces the pre-transaction validate_by_refresh_jti()
        # check — validation + locking happen atomically in one query.
        with transaction.atomic():
            try:
                SessionService.lock_for_rotation(jti)
            except Exception:
                raise AuthenticationFailed('Session is no longer active. Please log in again.')

            # Step 1 — kill the old refresh token
            JWTService.blacklist_refresh_token(refresh_token)
            # Step 2 — close the old server-side session (cache invalidated on_commit)
            SessionService.close(jti)
            # Step 3 — mint a new token pair (pure in-memory)
            new_tokens = JWTService.generate_tokens(user)
            # Step 4 — open the new server-side session
            SessionService.create(
                user,
                new_tokens['jti'],
                request,
                access_jti=new_tokens['access_jti'],
            )


        # Audit is intentionally OUTSIDE the transaction.
        # A logging failure here must never roll back a completed rotation.
        AuditService.log(
            event    = AuditLog.Event.TOKEN_REFRESH,
            user     = user,
            request  = request,
            metadata = {'old_jti_prefix': jti[:8]},
        )

        return new_tokens