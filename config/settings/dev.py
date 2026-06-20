"""
Development settings for CMS project.
Extends base settings with dev-specific overrides.
"""

from .base import *  # noqa: F401, F403

# =============================================================
# DEBUG
# =============================================================
DEBUG = True

# =============================================================
# ADDITIONAL DEV APPS
# =============================================================
# INSTALLED_APPS += []

# =============================================================
# EMAIL — Console backend for development
# =============================================================
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# =============================================================
# LOGGING
# =============================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Set to DEBUG to see SQL queries
            'propagate': False,
        },
    },
}
