import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import expense_store
import order_store
import product_store
import store_context
from store_context import current_store_id, resolve_data_file, use_store, validate_store_id


class StoreContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(store_context, "DATA_ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_default_store_keeps_legacy_paths(self):
        legacy = self.root / "legacy-products.json"
        with use_store("default"):
            self.assertEqual(resolve_data_file("products.json", legacy), legacy)

    def test_store_ids_reject_invalid_values(self):
        for value in ("store/other", "", "A Store", ".", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_store_id(value)

    def test_product_catalogs_are_isolated_between_stores(self):
        with use_store("alpha"):
            product_store.save_products([{"id": "alpha-item", "name": "Alpha"}])
        with use_store("beta"):
            product_store.save_products([{"id": "beta-item", "name": "Beta"}])
        with use_store("alpha"):
            self.assertEqual([p["id"] for p in product_store.load_products()], ["alpha-item"])
        with use_store("beta"):
            self.assertEqual([p["id"] for p in product_store.load_products()], ["beta-item"])

    def test_orders_and_inventory_paths_are_isolated_between_stores(self):
        with use_store("alpha"):
            order_store.save_orders([{"id": "alpha-order"}])
            path = order_store._products_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[{"id":"alpha-product"}]', encoding="utf-8")
        with use_store("beta"):
            order_store.save_orders([{"id": "beta-order"}])
            path = order_store._products_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[{"id":"beta-product"}]', encoding="utf-8")
        with use_store("alpha"):
            self.assertEqual(order_store.load_orders()[0]["id"], "alpha-order")
            self.assertIn("alpha-product", order_store._products_file().read_text(encoding="utf-8"))
        with use_store("beta"):
            self.assertEqual(order_store.load_orders()[0]["id"], "beta-order")
            self.assertIn("beta-product", order_store._products_file().read_text(encoding="utf-8"))

    def test_expense_ledgers_are_isolated_between_stores(self):
        with use_store("alpha"):
            expense_store.create_expense({"description": "Alpha expense", "amount": 100})
        with use_store("beta"):
            expense_store.create_expense({"description": "Beta expense", "amount": 200})
        with use_store("alpha"):
            self.assertEqual([e["description"] for e in expense_store.load_expenses()], ["Alpha expense"])
        with use_store("beta"):
            self.assertEqual([e["description"] for e in expense_store.load_expenses()], ["Beta expense"])

    def test_store_context_resets_after_exit(self):
        self.assertEqual(current_store_id(), "default")
        with use_store("alpha"):
            self.assertEqual(current_store_id(), "alpha")
        self.assertEqual(current_store_id(), "default")


if __name__ == "__main__":
    unittest.main()
