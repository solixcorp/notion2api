import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import is_lite_mode, is_standard_mode

# Set DISABLE_RATE_LIMIT=true to disable rate limiting (for debugging)
_disable_flag = os.getenv("DISABLE_RATE_LIMIT", "").strip().lower()
_rate_limit_disabled = _disable_flag == "true"

# Set rate limit dynamically based on APP_MODE
# Lite:     30/minute (fast single-turn, ~3-5s per request)
# Standard: 25/minute (full context with thinking and search)
# Heavy:    20/minute (includes database operations, slower)
if is_lite_mode():
    default_limit = "30/minute"
elif is_standard_mode():
    default_limit = "25/minute"
else:
    default_limit = "20/minute"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[] if _rate_limit_disabled else [default_limit],
    enabled=not _rate_limit_disabled,
)
