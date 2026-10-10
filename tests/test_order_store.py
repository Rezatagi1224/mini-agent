import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import order_store


class OrderStoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.orders_file = root / "orders.json"
        self.products_file = root / "products.json"
        self.orders_patch = patch.object(order_store, "DATA_FILE", self.orders_file)
        self.products_patch = patch.object(order_store, "PRODUCTS_FILE", self.products_file)
        self.orders_patch.start()
        self.products_patch.start()
        self.addCleanup(self.orders_patch.stop)
        self.addCleanup(self.products_patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.product = {
            "id": "shirt-1",
            "name": "تی‌شرت باکسی",
            "price": 500000,
            "currency": "تومان",
            "sizes": ["L", "XL"],
            "colors": ["مشکی", "سفید"],
            "stock": 20,
            "stock_by_variant": {"مشکی|L": 3, "مشکی|XL": 0, "سفید|L": 4, "سفید|XL": 2},
        }
        self.write_products([self.product])

    def write_products(self, products):
        self.products_file.parent.mkdir(parents=True, exist_ok=True)
        self.products_file.write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    def read_products(self):
        return json.loads(self.products_file.read_text(encoding="utf-8"))

    def make_order(self, *, size="L", color="مشکی", quantity=2):
        return order_store.create_order(
            customer_name="مشتری آزمایشی",
            phone="09123456789",
            address="تهران، خیابان نمونه، پلاک ۱۲",
            product=self.product,
            size=size,
            color=color,
            quantity=quantity,
        )

    def test_order_starts_pending_and_does_not_deduct_stock(self):
        order = self.make_order(quantity=2)
        self.assertEqual(order["status"], "pending")
        self.assertFalse(order["inventory_deducted"])
        self.assertEqual(self.read_products()[0]["stock_by_variant"]["مشکی|L"], 3)

    def test_confirmation_deducts_variant_stock_once(self):
        order = self.make_order(quantity=2)
        updated = order_store.update_order_status(order["id"], "confirmed")
        self.assertTrue(updated["inventory_deducted"])
        self.assertEqual(self.read_products()[0]["stock_by_variant"]["مشکی|L"], 1)

        # Repeating the same transition must not deduct inventory twice.
        order_store.update_order_status(order["id"], "confirmed")
        self.assertEqual(self.read_products()[0]["stock_by_variant"]["مشکی|L"], 1)

    def test_cancelling_confirmed_order_restores_stock_once(self):
        order = self.make_order(quantity=2)
        order_store.update_order_status(order["id"], "confirmed")
        cancelled = order_store.update_order_status(order["id"], "cancelled")
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertFalse(cancelled["inventory_deducted"])
        self.assertEqual(self.read_products()[0]["stock_by_variant"]["مشکی|L"], 3)

        order_store.update_order_status(order["id"], "cancelled")
        self.assertEqual(self.read_products()[0]["stock_by_variant"]["مشکی|L"], 3)

    def test_confirmation_fails_if_variant_stock_is_insufficient(self):
        order = self.make_order(quantity=4)
        with self.assertRaisesRegex(ValueError, "موجودی کافی نیست"):
            order_store.update_order_status(order["id"], "confirmed")
        saved = order_store.load_orders()[0]
        self.assertEqual(saved["status"], "pending")
        self.assertEqual(self.read_products()[0]["stock_by_variant"]["مشکی|L"], 3)

    def test_confirmation_fails_when_variant_stock_is_not_recorded(self):
        order = self.make_order(size="XL", color="سفید", quantity=1)
        products = self.read_products()
        del products[0]["stock_by_variant"]["سفید|XL"]
        self.write_products(products)

        with self.assertRaisesRegex(ValueError, "موجودی دقیق"):
            order_store.update_order_status(order["id"], "confirmed")
        self.assertEqual(order_store.load_orders()[0]["status"], "pending")

    def test_terminal_status_cannot_be_reopened(self):
        order = self.make_order(quantity=1)
        order_store.update_order_status(order["id"], "cancelled")
        with self.assertRaisesRegex(ValueError, "تغییر وضعیت مجاز نیست"):
            order_store.update_order_status(order["id"], "confirmed")

    def test_invalid_contact_and_quantity_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "شماره تماس معتبر نیست"):
            order_store.create_order(
                customer_name="مشتری آزمایشی",
                phone="not-a-phone",
                address="تهران، خیابان نمونه، پلاک ۱۲",
                product=self.product,
                size="L",
                color="مشکی",
                quantity=1,
            )
        with self.assertRaisesRegex(ValueError, "بین ۱ تا ۲۰"):
            self.make_order(quantity=21)


if __name__ == "__main__":
    unittest.main()
