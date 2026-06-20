"""
Step 5 — System-wide constants.

Magic numbers, prefixes, and limits live here so they are defined once
and reused everywhere.
"""

# ---------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ---------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------
# Max size in bytes (5 MB).
MAX_UPLOAD_SIZE = 5 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]

# ---------------------------------------------------------------
# ID / code prefixes
# ---------------------------------------------------------------
STUDENT_ID_PREFIX = "STU"
FACULTY_ID_PREFIX = "FAC"
RECEIPT_PREFIX = "RCPT"

# ---------------------------------------------------------------
# Validation
# ---------------------------------------------------------------
# Nepal phone numbers: 10 digits, optional +977 country code.
PHONE_REGEX = r"^(\+977[- ]?)?\d{10}$"
