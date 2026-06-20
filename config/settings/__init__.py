from .base import *  # noqa: F401, F403

# Import dev settings by default
try:
    from .dev import *  # noqa: F401, F403
except ImportError:
    pass
