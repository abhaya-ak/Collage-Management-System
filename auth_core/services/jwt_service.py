# auth_core/services/jwt_service.py
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
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
                'access':      str,   # short-lived access token string
                'refresh':     str,   # long-lived refresh token string
                'jti':         str,   # jti of the REFRESH token (session anchor)
                'access_jti':  str,   # jti of the ACCESS token (middleware check)
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
    def blacklist_refresh_token(refresh_token_str: str) -> str | None:
        """
        Writes the refresh token's jti to TokenBlacklist.
        Returns the jti on success, None if the token is invalid/expired.
        Safe to call multiple times for the same token (get_or_create is idempotent).
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