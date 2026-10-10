import unittest

from admin_auth import (
    AdminLoginRateLimiter,
    ADMIN_SESSION_TTL_SECONDS,
    create_admin_session_token,
    verify_admin_password,
    verify_admin_session_token,
)


class AdminAuthTests(unittest.TestCase):
    def test_password_requires_configured_secret_and_exact_match(self):
        self.assertTrue(verify_admin_password("correct horse", "correct horse"))
        self.assertFalse(verify_admin_password("wrong", "correct horse"))
        self.assertFalse(verify_admin_password("anything", ""))
        self.assertFalse(verify_admin_password(None, "correct horse"))
        self.assertFalse(verify_admin_password("correct horse", None))

    def test_valid_session_is_accepted_until_expiration(self):
        now = 1_800_000_000
        token = create_admin_session_token("test-secret", now=now)
        self.assertTrue(verify_admin_session_token(token, "test-secret", now=now))
        self.assertTrue(
            verify_admin_session_token(
                token, "test-secret", now=now + ADMIN_SESSION_TTL_SECONDS - 1
            )
        )

    def test_expired_session_is_rejected(self):
        now = 1_800_000_000
        token = create_admin_session_token("test-secret", now=now)
        self.assertFalse(
            verify_admin_session_token(
                token, "test-secret", now=now + ADMIN_SESSION_TTL_SECONDS
            )
        )

    def test_tampered_or_malformed_sessions_are_rejected(self):
        token = create_admin_session_token("test-secret", now=1_800_000_000)
        expiry, signature = token.split(".", 1)
        tampered_signature = ("0" if signature[0] != "0" else "1") + signature[1:]
        self.assertFalse(
            verify_admin_session_token(
                f"{expiry}.{tampered_signature}",
                "test-secret",
                now=1_800_000_000,
            )
        )
        self.assertFalse(verify_admin_session_token("not-a-token", "test-secret"))
        self.assertFalse(verify_admin_session_token(token, "other-secret", now=1_800_000_000))
        self.assertFalse(verify_admin_session_token(token, "", now=1_800_000_000))

    def test_session_token_is_not_valid_after_password_rotation(self):
        token = create_admin_session_token("old-secret", now=1_800_000_000)
        self.assertFalse(
            verify_admin_session_token(token, "new-secret", now=1_800_000_000)
        )


    def test_login_limiter_blocks_after_max_failures_and_reports_retry_after(self):
        limiter = AdminLoginRateLimiter(max_attempts=3, window_seconds=60)
        for timestamp in (100, 110, 120):
            self.assertTrue(limiter.is_allowed("192.0.2.1", now=timestamp))
            limiter.record_failure("192.0.2.1", now=timestamp)

        self.assertFalse(limiter.is_allowed("192.0.2.1", now=121))
        self.assertEqual(limiter.retry_after("192.0.2.1", now=121), 39)
        self.assertTrue(limiter.is_allowed("192.0.2.1", now=160))

    def test_login_limiter_clears_failures_after_success(self):
        limiter = AdminLoginRateLimiter(max_attempts=2, window_seconds=60)
        limiter.record_failure("192.0.2.2", now=10)
        limiter.record_failure("192.0.2.2", now=11)
        self.assertFalse(limiter.is_allowed("192.0.2.2", now=12))

        limiter.clear("192.0.2.2")
        self.assertTrue(limiter.is_allowed("192.0.2.2", now=12))
        self.assertEqual(limiter.retry_after("192.0.2.2", now=12), 0)

    def test_login_limiter_tracks_clients_separately_and_caps_client_keys(self):
        limiter = AdminLoginRateLimiter(max_attempts=1, window_seconds=60, max_clients=1)
        limiter.record_failure("192.0.2.3", now=1)
        self.assertFalse(limiter.is_allowed("192.0.2.3", now=2))
        self.assertTrue(limiter.is_allowed("192.0.2.4", now=2))


    def test_session_claims_bind_token_to_store_and_role(self):
        now = 1_800_000_000
        token = create_admin_session_token(
            "test-secret", store_id="shop-02", role="store_admin", now=now
        )
        from admin_auth import read_admin_session_token
        self.assertEqual(
            read_admin_session_token(token, "test-secret", now=now),
            {"store_id": "shop-02", "role": "store_admin", "expires_at": now + ADMIN_SESSION_TTL_SECONDS},
        )
        self.assertFalse(verify_admin_session_token(token, "other-secret", now=now))

    def test_session_store_or_role_cannot_be_tampered(self):
        now = 1_800_000_000
        token = create_admin_session_token(
            "test-secret", store_id="shop-02", role="store_admin", now=now
        )
        parts = token.split(".")
        parts[3] = "shop-03"
        from admin_auth import read_admin_session_token
        self.assertIsNone(read_admin_session_token(".".join(parts), "test-secret", now=now))
        parts = token.split(".")
        parts[2] = "owner"
        self.assertIsNone(read_admin_session_token(".".join(parts), "test-secret", now=now))

if __name__ == "__main__":
    unittest.main()
