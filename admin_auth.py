"""Short-lived, signed admin sessions for the Mini Agent web UI."""
import hashlib
import hmac
import math
import time
from collections import OrderedDict, deque

ADMIN_SESSION_COOKIE = "mini_agent_admin_session"
ADMIN_SESSION_TTL_SECONDS = 8 * 60 * 60
_SESSION_CONTEXT = b"mini-agent-admin-session:"


def verify_admin_password(supplied: object, expected: object) -> bool:
    """Compare configured admin credentials without leaking timing information."""
    if not isinstance(supplied, str) or not isinstance(expected, str) or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


def _valid_expiry(expires_at: int, current_time: float) -> bool:
    return (
        expires_at > int(current_time)
        and expires_at <= int(current_time) + ADMIN_SESSION_TTL_SECONDS + 1
    )


def _verify_v2_session(token: object, signing_secret: object, *, now: float | None = None):
    if not isinstance(token, str) or not isinstance(signing_secret, str) or not signing_secret:
        return None
    parts = token.split(".")
    if len(parts) != 5 or parts[0] != "v2":
        return None
    _, expiry_text, role, store_id, supplied_signature = parts
    try:
        expires_at = int(expiry_text)
        from store_context import validate_store_id
        validate_store_id(store_id)
    except (ValueError, TypeError):
        return None
    if role not in ("owner", "store_admin"):
        return None
    current_time = time.time() if now is None else now
    if not _valid_expiry(expires_at, current_time):
        return None
    body = ".".join(parts[:4])
    expected_signature = hmac.new(
        signing_secret.encode("utf-8"),
        _SESSION_CONTEXT + body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    return {"store_id": store_id, "role": role, "expires_at": expires_at}


def create_admin_session_token(
    password: str,
    *,
    store_id: str = "default",
    role: str = "owner",
    now: float | None = None,
) -> str:
    """Create a signed, short-lived token bound to a role and a single store."""
    from store_context import validate_store_id

    if not isinstance(password, str) or not password:
        raise ValueError("An admin session signing secret must be configured.")
    validate_store_id(store_id)
    if role not in ("owner", "store_admin"):
        raise ValueError("Invalid administrator role.")
    issued_at = time.time() if now is None else now
    expires_at = int(issued_at + ADMIN_SESSION_TTL_SECONDS)
    body = f"v2.{expires_at}.{role}.{store_id}"
    signature = hmac.new(
        password.encode("utf-8"),
        _SESSION_CONTEXT + body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{signature}"


def read_admin_session_token(
    token: object,
    signing_secret: object,
    *,
    now: float | None = None,
) -> dict | None:
    """Return trusted role/store claims for a valid token, otherwise None.

    Legacy two-part tokens are accepted only as owner access to the default store
    so existing signed-in sessions continue to work until they expire.
    """
    session = _verify_v2_session(token, signing_secret, now=now)
    if session is not None:
        return session
    if not isinstance(token, str) or not isinstance(signing_secret, str) or not signing_secret:
        return None
    try:
        expiry_text, supplied_signature = token.split(".", 1)
        expires_at = int(expiry_text)
    except (ValueError, TypeError):
        return None
    if not _valid_expiry(expires_at, time.time() if now is None else now):
        return None
    expected_signature = hmac.new(
        signing_secret.encode("utf-8"),
        _SESSION_CONTEXT + expiry_text.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(supplied_signature, expected_signature):
        return {"store_id": "default", "role": "owner", "expires_at": expires_at}
    return None


def verify_admin_session_token(
    token: object,
    expected_password: object,
    *,
    now: float | None = None,
) -> bool:
    """Verify session integrity, expiration, and the current signing secret."""
    return read_admin_session_token(token, expected_password, now=now) is not None


class AdminLoginRateLimiter:
    """Bounded process-local limiter for failed administrator login attempts."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: int = 15 * 60,
        max_clients: int = 2048,
    ):
        if max_attempts < 1 or window_seconds < 1 or max_clients < 1:
            raise ValueError("Rate-limit settings must be positive.")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._failures: OrderedDict[str, deque[float]] = OrderedDict()

    @staticmethod
    def _key(client_key: object) -> str:
        if not isinstance(client_key, str) or not client_key.strip():
            return "unknown"
        return client_key.strip()[:200]

    def _active_attempts(self, key: str, current_time: float) -> deque[float]:
        attempts = self._failures.get(key)
        if attempts is None:
            return deque()

        cutoff = current_time - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()

        if not attempts:
            self._failures.pop(key, None)
            return deque()

        self._failures.move_to_end(key)
        return attempts

    def is_allowed(self, client_key: object, *, now: float | None = None) -> bool:
        key = self._key(client_key)
        current_time = time.time() if now is None else now
        return len(self._active_attempts(key, current_time)) < self.max_attempts

    def retry_after(self, client_key: object, *, now: float | None = None) -> int:
        key = self._key(client_key)
        current_time = time.time() if now is None else now
        attempts = self._active_attempts(key, current_time)
        if len(attempts) < self.max_attempts:
            return 0
        return max(1, math.ceil(attempts[0] + self.window_seconds - current_time))

    def record_failure(self, client_key: object, *, now: float | None = None) -> None:
        key = self._key(client_key)
        current_time = time.time() if now is None else now
        self._active_attempts(key, current_time)

        if key not in self._failures and len(self._failures) >= self.max_clients:
            self._failures.popitem(last=False)
        self._failures.setdefault(key, deque()).append(current_time)
        self._failures.move_to_end(key)

    def clear(self, client_key: object) -> None:
        self._failures.pop(self._key(client_key), None)
