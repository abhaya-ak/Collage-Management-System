# auth_core/services/jwt_service.py
import base64
import json

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, UntypedToken
from rest_framework_simplejwt.exceptions import TokenError


class JWTService:
    """
    Wraps simplejwt. Does NOT re-implement JWT crypto.
    Provides a clean interface so the rest of the codebase
    never imports simplejwt internals directly.
    """

    @staticmethod
    def generate_tokens(user) -> dict:
        """
        Returns:
            {
                'access':      str,   # short-lived access token
                'refresh':     str,   # long-lived refresh token
                'jti':         str,   # jti of the REFRESH token (used for sessions)
                'access_jti':  str,   # jti of the access token
            }
        """
        refresh = RefreshToken.for_user(user)
        access  = refresh.access_token
        return {
            'access':     str(access),
            'refresh':    str(refresh),
            'jti':        str(refresh['jti']),
            'access_jti': str(access['jti']),
        }

    @staticmethod
    def extract_jti_unsafe(token: str) -> str | None:
        """
        Decode JWT payload WITHOUT signature verification.
        Used only for the fast blacklist check in AuthMiddleware —
        DRF still performs full cryptographic verification for every request.
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            # Pad base64url to a multiple of 4
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            return str(decoded.get('jti', '')) or None
        except Exception:
            return None

    @staticmethod
    def blacklist_refresh_token(refresh_token_str: str) -> str | None:
        """
        Writes the refresh token's jti to TokenBlacklist.
        Returns the jti on success, None if the token is invalid.
        """
        from auth_core.models import TokenBlacklist
        try:
            refresh    = RefreshToken(refresh_token_str)
            jti        = str(refresh['jti'])
            expires_at = timezone.datetime.fromtimestamp(
                refresh['exp'], tz=timezone.utc
            )
            TokenBlacklist.objects.get_or_create(
                jti=jti,
                defaults={'expires_at': expires_at},
            )
            return jti
        except TokenError:
            return None

    @staticmethod
    def is_blacklisted(jti: str) -> bool:
        from auth_core.models import TokenBlacklist
        return TokenBlacklist.objects.filter(jti=jti).exists()