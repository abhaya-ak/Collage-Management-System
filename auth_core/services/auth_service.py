# auth_core/services/auth_service.py
from django.contrib.auth import authenticate, get_user_model
from rest_framework.exceptions import AuthenticationFailed

from auth_core.models import AuditLog, UserProfile
from auth_core.services.jwt_service import JWTService
from auth_core.services.session_service import SessionService
from auth_core.services.audit_service import AuditService
from users.models import Role, UserRole

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
        1. Create User
        2. Create UserProfile
        3. Assign 'student' role (get_or_create so it's idempotent)
        4. Generate JWT tokens
        5. Create UserSession (refresh jti)
        6. Audit log REGISTER
        Returns: {'user': User, 'access': str, 'refresh': str, 'jti': str}
        """
        user = User.objects.create_user(
            username   = validated_data['username'],
            email      = validated_data.get('email', ''),
            password   = validated_data['password'],
            first_name = validated_data.get('first_name', ''),
            last_name  = validated_data.get('last_name', ''),
        )

        UserProfile.objects.create(user=user)

        # Default role: student
        role, _ = Role.objects.get_or_create(name='student')
        UserRole.objects.create(user=user, role=role)

        tokens = JWTService.generate_tokens(user)
        SessionService.create(user, tokens['jti'], request)

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
        1. authenticate() — Django's built-in credential check
        2. If fail: log LOGIN_FAILED, raise AuthenticationFailed
        3. If inactive: raise AuthenticationFailed
        4. Generate tokens, create session, log LOGIN
        Returns: {'user': User, 'access': str, 'refresh': str, 'jti': str}
        """
        user = authenticate(request=request, username=username, password=password)

        if user is None:
            AuditService.log(
                event    = AuditLog.Event.LOGIN_FAILED,
                request  = request,
                metadata = {'username_attempted': username},
            )
            raise AuthenticationFailed('Invalid username or password.')

        if not user.is_active:
            raise AuthenticationFailed('This account has been deactivated.')

        tokens = JWTService.generate_tokens(user)
        SessionService.create(user, tokens['jti'], request)

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
        1. Blacklist the refresh token jti
        2. Close the UserSession for that jti
        3. Log LOGOUT

        Does NOT raise on invalid token — logout should always succeed
        from the UX perspective (idempotent).
        """
        jti = JWTService.blacklist_refresh_token(refresh_token)
        if jti:
            SessionService.close(jti)
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

        if not SessionService.validate(jti):
            raise AuthenticationFailed('Session is no longer active. Please log in again.')

        try:
            user = User.objects.get(pk=refresh['user_id'])
        except User.DoesNotExist:
            raise AuthenticationFailed('User account not found.')

        # Rotate: close old session + blacklist old token
        JWTService.blacklist_refresh_token(refresh_token)
        SessionService.close(jti)

        # Open new session
        new_tokens = JWTService.generate_tokens(user)
        SessionService.create(user, new_tokens['jti'], request)

        AuditService.log(
            event    = AuditLog.Event.TOKEN_REFRESH,
            user     = user,
            request  = request,
            metadata = {'old_jti_prefix': jti[:8]},
        )

        return new_tokens