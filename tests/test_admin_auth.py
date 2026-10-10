import unittest

from admin_auth import (
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


if __name__ == "__main__":
    unittest.main()
