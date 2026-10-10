import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import product_store


class ProductStoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "products.json"
        self.patch = patch.object(product_store, "DATA_FILE", self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_missing_catalog_uses_seed_products(self):
        products = product_store.load_products()
        self.assertIsInstance(products, list)
        self.assertTrue(all(isinstance(item, dict) for item in products))

    def test_corrupt_catalog_is_not_replaced_by_seed_data(self):
        original = "{bad json"
        self.path.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "قابل خواندن نیست"):
            product_store.load_products()
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_invalid_catalog_shape_is_rejected_and_preserved(self):
        original = json.dumps({"not": "a list"})
        self.path.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "ساختار"):
            product_store.load_products()
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
