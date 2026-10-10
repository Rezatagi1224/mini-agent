import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import store_registry


class StoreRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Path(self.temp.name) / "registry.json"
        self.patch = patch.object(store_registry, "REGISTRY_FILE", self.registry)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_create_store_hashes_password_and_authenticates(self):
        created = store_registry.create_store("shop-a", "فروشگاه الف", "a-very-long-test-password")
        self.assertEqual(created["store_id"], "shop-a")
        self.assertTrue(created["active"])
        self.assertTrue(store_registry.verify_store_password("shop-a", "a-very-long-test-password"))
        self.assertFalse(store_registry.verify_store_password("shop-a", "wrong-password"))
        saved = self.registry.read_text(encoding="utf-8")
        self.assertNotIn("a-very-long-test-password", saved)
        record = json.loads(saved)["stores"]["shop-a"]
        self.assertNotIn("password", record)
        self.assertIn("password_hash", record)
        self.assertIn("salt", record)

    def test_default_id_is_reserved_and_store_ids_are_validated(self):
        with self.assertRaises(ValueError):
            store_registry.create_store("default", "فروشگاه اصلی", "a-very-long-test-password")
        with self.assertRaises(ValueError):
            store_registry.create_store("../oops", "نام", "a-very-long-test-password")
        with self.assertRaises(ValueError):
            store_registry.create_store("shop-b", "نام", "short")

    def test_duplicate_id_is_rejected_without_overwriting_credentials(self):
        store_registry.create_store("shop-a", "الف", "password-older-long")
        with self.assertRaisesRegex(ValueError, "قبلاً"):
            store_registry.create_store("shop-a", "نام جدید", "password-newer-long")
        self.assertTrue(store_registry.verify_store_password("shop-a", "password-older-long"))
        self.assertFalse(store_registry.verify_store_password("shop-a", "password-newer-long"))

    def test_disabled_store_rejects_login_and_can_be_reenabled(self):
        store_registry.create_store("shop-a", "الف", "a-very-long-test-password")
        store_registry.set_store_active("shop-a", False)
        self.assertFalse(store_registry.is_store_active("shop-a"))
        self.assertFalse(store_registry.verify_store_password("shop-a", "a-very-long-test-password"))
        self.assertIsNone(store_registry.get_store("shop-a", include_inactive=False))
        store_registry.set_store_active("shop-a", True)
        self.assertTrue(store_registry.is_store_active("shop-a"))
        self.assertTrue(store_registry.verify_store_password("shop-a", "a-very-long-test-password"))

    def test_password_reset_invalidates_old_password(self):
        store_registry.create_store("shop-a", "الف", "a-very-long-test-password")
        store_registry.reset_store_password("shop-a", "a-different-long-password")
        self.assertFalse(store_registry.verify_store_password("shop-a", "a-very-long-test-password"))
        self.assertTrue(store_registry.verify_store_password("shop-a", "a-different-long-password"))

    def test_corrupt_registry_fails_closed(self):
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        self.registry.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "قابل خواندن نیست"):
            store_registry.create_store("shop-a", "الف", "a-very-long-test-password")
        self.assertEqual(self.registry.read_text(encoding="utf-8"), "{broken")


if __name__ == "__main__":
    unittest.main()
