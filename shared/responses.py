"""
Standardized API response envelope.

Every endpoint returns the same shape:
    {
        "success": bool,
        "message": str,
        "data": <payload> | null,
        "errors": <details> | null   # only on failures
    }
"""

from rest_framework.response import Response


def success_response(data=None, message="Success", status_code=200) -> Response:
    return Response(
        {"success": True, "message": message, "data": data},
        status=status_code,
    )


def error_response(message="Error", errors=None, status_code=400) -> Response:
    return Response(
        {"success": False, "message": message, "data": None, "errors": errors},
        status=status_code,
    )
