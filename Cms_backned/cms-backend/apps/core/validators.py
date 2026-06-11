"""
Step 7 — Reusable field validators.

Used by students / faculty / fees (file uploads, phone numbers, etc.).
These raise django.core.exceptions.ValidationError so they plug directly into
model fields and serializers.
"""

import os
import re

from django.core.exceptions import ValidationError

from apps.core.constants import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    PHONE_REGEX,
)


def _extension(value) -> str:
    """Lowercase file extension without the dot."""
    return os.path.splitext(value.name)[1].lower().lstrip(".")


def validate_file_size(value):
    """Reject files larger than MAX_UPLOAD_SIZE."""
    if value.size > MAX_UPLOAD_SIZE:
        limit_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
        raise ValidationError(f"File too large. Maximum size is {limit_mb:.0f} MB.")


def validate_image(value):
    """Validate an uploaded image: allowed extension + size limit."""
    ext = _extension(value)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image type '.{ext}'. "
            f"Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}."
        )
    validate_file_size(value)


def validate_document(value):
    """Validate an uploaded document: allowed extension + size limit."""
    ext = _extension(value)
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            f"Unsupported document type '.{ext}'. "
            f"Allowed: {', '.join(ALLOWED_DOCUMENT_EXTENSIONS)}."
        )
    validate_file_size(value)


def validate_phone_number(value):
    """Validate a Nepal phone number (10 digits, optional +977)."""
    if not re.match(PHONE_REGEX, str(value)):
        raise ValidationError("Enter a valid phone number (e.g. 9812345678).")
