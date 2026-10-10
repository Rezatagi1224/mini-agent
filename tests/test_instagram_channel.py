import json
import unittest
from unittest.mock import patch

from instagram_channel import extract_text_messages, resolve_instagram_account


class InstagramStoreRoutingTests(unittest.TestCase):
    def test_extracts_recipient_account_id(self):
        payload = {
            "entry": [{
                "id": "business-123",
                "messaging": [{
                    "sender": {"id": "customer-7"},
                    "recipient": {"id": "business-123"},
                    "message": {"mid": "m-1", "text": "سلام"},
                }],
            }]
        }
        messages = extract_text_messages(payload)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["sender_id"], "customer-7")
        self.assertEqual(messages[0]["recipient_id"], "business-123")

    def test_multiple_accounts_route_only_to_configured_store(self):
        config = {
            "business-1": {"store_id": "default", "access_token": "token-one"},
            "business-2": {"store_id": "shop-2", "access_token": "token-two"},
        }
        with patch.dict("os.environ", {
            "INSTAGRAM_ACCOUNTS_JSON": json.dumps(config),
            "INSTAGRAM_ACCESS_TOKEN": "fallback-token",
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "legacy-account",
        }, clear=True):
            self.assertEqual(
                resolve_instagram_account("business-2"),
                {"account_id": "business-2", "store_id": "shop-2", "access_token": "token-two"},
            )
            self.assertEqual(
                resolve_instagram_account("business-1")["store_id"],
                "default",
            )
            self.assertIsNone(resolve_instagram_account("unknown-business"))

    def test_multi_account_config_rejects_invalid_json(self):
        with patch.dict("os.environ", {"INSTAGRAM_ACCOUNTS_JSON": "not json"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "valid JSON"):
                resolve_instagram_account("business-1")

    def test_legacy_single_account_routes_only_its_account_to_default(self):
        with patch.dict("os.environ", {
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "legacy-account",
            "INSTAGRAM_ACCESS_TOKEN": "legacy-token",
        }, clear=True):
            self.assertEqual(
                resolve_instagram_account("legacy-account"),
                {"account_id": "legacy-account", "store_id": "default", "access_token": "legacy-token"},
            )
            self.assertIsNone(resolve_instagram_account("other-account"))


if __name__ == "__main__":
    unittest.main()
