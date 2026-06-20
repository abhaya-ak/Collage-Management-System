"""
Step 6 — Standardized error layer.

Raise these from services/views instead of generic errors. All inherit DRF's
APIException, so DRF renders them with the correct HTTP status and a consistent
JSON shape.

    raise BusinessRuleViolation("Cannot enroll: semester is closed.")
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class CoreException(APIException):
    """Base for all custom CMS exceptions."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred."
    default_code = "error"


class ValidationException(CoreException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid input."
    default_code = "validation_error"


class BusinessRuleViolation(CoreException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This action violates a business rule."
    default_code = "business_rule_violation"


class InvalidOperation(CoreException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This operation is not allowed in the current state."
    default_code = "invalid_operation"


class PermissionDeniedException(CoreException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"
