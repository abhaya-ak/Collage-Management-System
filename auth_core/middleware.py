# auth_core/middleware.py
import json
import base64
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

# Paths that carry no access token — skip session check entirely
_EXEMPT_PREFIXES = (
    '/api/v1/auth/login/',
    '/api/v1/auth/register/',
    '/api/v1/auth/refresh/',
    '/api/v1/auth/logout/',   # exempt so revoked sessions can still blacklist their refresh token
    '/admin/',
)

# Session validity is cached for this many seconds.
# Revocation (logout / password change) deletes the cache key via on_commit,
# so effective revocation latency is ~0ms, not the full TTL.
# Raise this value to reduce DB reads at the cost of a larger revocation window
# if cache invalidation fails (e.g. Redis is unreachable).
_SESSION_CACHE_TTL = 30  # seconds

# Cache key format — must match the key used in SessionService.close()
_SESSION_CACHE_KEY = 'auth:session:{jti}'


class AuthMiddleware(MiddlewareMixin):
    """
    Unified single-source-of-truth enforcement layer.

    Responsibility split (Issue 2 fix):
        Layer 1 — AuthMiddleware (THIS FILE)
          Question  : Is this session STILL ALLOWED?
          Mechanism : Cache → DB positive assertion on UserSession.access_jti
          Decision  : No active session → 401 immediately

        Layer 2 — DRF JWTAuthentication (simplejwt)
          Question  : Is the token CRYPTOGRAPHICALLY VALID?
          Mechanism : HS256 signature + exp + claims
          Decision  : Invalid/expired → 401

    Both layers must pass. Neither alone is sufficient.

    DB load reduction (Issue 4 fix):
        Session validity is cached (TTL=30s, Redis in prod).
        Cache is invalidated via transaction.on_commit() on logout / password change,
        so revocation takes effect within milliseconds of commit, not 30s.

    Trust model (Issue 6 fix):
        The jti extracted here is base64-decoded WITHOUT signature verification.
        It is stored as request._unverified_access_jti — the name communicates
        that it has NOT been cryptographically validated. Never use it for
        authorization decisions; use it only as a cache/DB lookup key.
        DRF's JWTAuthentication performs full HS256 verification independently.
    """

    def process_request(self, request):
        if any(request.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return None

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[7:].strip()
        if not token:
            return None

        # Extract jti WITHOUT signature verification (fast path).
        # Named 'unverified' to prevent downstream trust confusion (Issue 6).
        jti = self._extract_jti_fast(token)
        if not jti:
            return None  # Malformed — let DRF return the proper error

        # ── CACHE CHECK (Issue 4) ─────────────────────────────────────────────
        # Check cache before hitting the DB. Cache is invalidated on_commit
        # when a session is closed, so revocation is effectively immediate.
        from django.core.cache import cache
        cache_key = _SESSION_CACHE_KEY.format(jti=jti)
        is_active = cache.get(cache_key)

        if is_active is None:
            # Cache miss — query DB and populate cache
            from auth_core.models import UserSession
            is_active = UserSession.objects.filter(
                access_jti=jti, is_active=True
            ).exists()
            cache.set(cache_key, is_active, _SESSION_CACHE_TTL)

        # ── POSITIVE ASSERTION (Issue 2) ──────────────────────────────────────
        if not is_active:
            return JsonResponse(
                {
                    'detail': 'Session not found or has been revoked. Please log in again.',
                    'code':   'session_invalid',
                },
                status=401,
            )

        # Attach for downstream use — name clearly marks it as unverified (Issue 6)
        request._unverified_access_jti = jti
        return None

    @staticmethod
    def _extract_jti_fast(token: str) -> str | None:
        """
        Decode JWT payload WITHOUT signature verification.
        JWT = base64url(header) . base64url(payload) . signature
        Full cryptographic verification is handled by DRF's JWTAuthentication.
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            return str(decoded.get('jti', '')) or None
        except Exception:
            return None
