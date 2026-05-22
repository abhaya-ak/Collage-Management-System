# auth_core/middleware.py
import json
import base64

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


# Paths where no blacklist check is needed (no valid token expected)
_EXEMPT_PREFIXES = (
    '/api/v1/auth/login/',
    '/api/v1/auth/register/',
    '/api/v1/auth/refresh/',
    '/admin/',
)


class AuthMiddleware(MiddlewareMixin):
    """
    Fast pre-DRF blacklist enforcement.

    For every request carrying a Bearer token:
      1. Extract the jti WITHOUT full JWT verification (no crypto, fast)
      2. Check TokenBlacklist — if present, return 401 immediately
      3. Attach request._auth_jti for downstream services (SessionService.touch)

    Full JWT verification (signature, expiry, claims) is still performed
    by DRF's JWTAuthentication backend on every request. This middleware
    only adds the blacklist check so that logout takes effect on the
    very next request — not after the access token expires.
    """

    def process_request(self, request):
        # Skip exempt paths
        if any(request.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return None

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None  # Unauthenticated request — let DRF handle it

        token = auth_header[7:].strip()
        if not token:
            return None

        jti = self._extract_jti_fast(token)
        if not jti:
            return None  # Malformed — let DRF return the proper error

        # Import here to avoid AppRegistryNotReady at module load time
        from auth_core.models import TokenBlacklist

        if TokenBlacklist.objects.filter(jti=jti).exists():
            return JsonResponse(
                {
                    'detail': 'Token has been revoked. Please log in again.',
                    'code':   'token_revoked',
                },
                status=401,
            )

        # Attach for downstream use (e.g. SessionService.touch in views)
        request._auth_jti = jti
        return None

    @staticmethod
    def _extract_jti_fast(token: str) -> str | None:
        """
        Decode JWT payload WITHOUT signature verification.
        JWT = base64url(header) . base64url(payload) . signature
        We only decode the payload segment to read the 'jti' claim.
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            payload = parts[1]
            # base64url padding
            payload += '=' * (4 - len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            return str(decoded.get('jti', '')) or None
        except Exception:
            return None
