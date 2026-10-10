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
