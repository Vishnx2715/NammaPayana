"""Shared Flask extension instances — initialized without an app, bound in create_app()."""
import functools
from flask import current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")
csrf = CSRFProtect()


@limiter.request_filter
def _rate_limit_exempt_when_disabled():
    """Skip rate limiting when RATELIMIT_ENABLED=False in the app config.
    Evaluated at each request so test fixtures can toggle it without restart."""
    try:
        return not current_app.config.get("RATELIMIT_ENABLED", True)
    except RuntimeError:
        return False


def csrf_protect_if_enabled(f):
    """Enforce CSRF only when WTF_CSRF_ENABLED is True (disabled in tests via config)."""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if current_app.config.get("WTF_CSRF_ENABLED", True):
            csrf.protect()
        return f(*args, **kwargs)
    return wrapped
