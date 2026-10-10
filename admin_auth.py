"""Short-lived, signed admin sessions for the Mini Agent web UI."""
import hashlib
import hmac
import time

ADMIN_SESSION_COOKIE = "mini_agent_admin_session"
ADMIN_SESSION_TTL_SECONDS = 8 * 60 * 60
_SESSION_CONTEXT = b"mini-agent-admin-session:"


def verify_admin_password(supplied: object, expected: object) -> bool:
    """Compare configured admin credentials without leaking timing information."""
    if not isinstance(supplied, str) or not isinstance(expected, str) or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


def create_admin_session_token(password: str, *, now: float | None = None) -> str:
    """Create a signed token expiring after eight hours."""
    if not isinstance(password, str) or not password:
        raise ValueError("An admin password must be configured.")
    issued_at = time.time() if now is None else now
    expires_at = int(issued_at + ADMIN_SESSION_TTL_SECONDS)
    payload = str(expires_at)
    signature = hmac.new(
        password.encode("utf-8"),
        _SESSION_CONTEXT + payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_admin_session_token(
    token: object,
    expected_password: object,
    *,
    now: float | None = None,
) -> bool:
    """Verify token integrity, expiration, and the current configured password."""
    if not isinstance(token, str) or not token or not isinstance(expected_password, str):
        return False
    if not expected_password:
        return False
    try:
        expiry_text, supplied_signature = token.split(".", 1)
        expires_at = int(expiry_text)
    except (ValueError, TypeError):
        return False
    current_time = time.time() if now is None else now
    if expires_at <= int(current_time):
        return False
    if expires_at > int(current_time) + ADMIN_SESSION_TTL_SECONDS + 1:
        return False
    expected_signature = hmac.new(
        expected_password.encode("utf-8"),
        _SESSION_CONTEXT + expiry_text.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(supplied_signature, expected_signature)
