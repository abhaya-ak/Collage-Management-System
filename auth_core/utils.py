# auth_core/utils.py
"""
Shared utility helpers for the auth_core app.
Centralised here so session_service.py and audit_service.py
don't each carry their own copy of the same function.
"""


def get_client_ip(request) -> str | None:
    """
    Extracts the real client IP from the request.
    Respects X-Forwarded-For for reverse-proxy deployments.
    Returns None if request is None or IP cannot be determined.
    """
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first (leftmost) address — that's the client IP
        # Addresses further right may be added by untrusted proxies
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
