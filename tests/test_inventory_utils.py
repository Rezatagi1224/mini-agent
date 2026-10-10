import unittest
from inventory_utils import stock_status, stock_message


class InventoryUtilsTests(unittest.TestCase):
    def setUp(self):
        self.product = {
            "id": "shirt-1", "name": "پیراهن",
            "sizes": ["L", "XL"], "colors": ["مشکی", "سفید"], "stock": 99,
            "stock_by_variant": {
                "مشکی|L": 2, "مشکی|XL": 0, "سفید|L": 5, "سفید|XL": 3,
            },
        }

    def test_exact_variant_is_checked_directly(self):
        self.assertEqual(stock_status(self.product, size="xl", color="مشکی"),
                         {"status": "out_of_stock", "quantity": 0, "scope": "variant"})

    def test_missing_variant_does_not_fall_back_to_total_stock(self):
        product = {"name": "تی‌شرت", "sizes": ["L", "XL"], "colors": ["مشکی"],
                   "stock": 20, "stock_by_variant": {"مشکی|L": 4}}
        result = stock_status(product, size="XL", color="مشکی")
        self.assertEqual(result["status"], "unverified")
        self.assertIsNone(result["quantity"])
        self.assertIn("قابل تأیید نیست", stock_message(product, size="XL", color="مشکی"))

    def test_partial_map_does_not_claim_size_aggregate_is_complete(self):
        product = {"name": "تی‌شرت", "sizes": ["L"], "colors": ["مشکی", "سفید"],
                   "stock_by_variant": {"مشکی|L": 4}}
        self.assertEqual(stock_status(product, size="L")["status"], "unverified")

    def test_complete_variant_map_can_be_aggregated(self):
        result = stock_status(self.product, size="XL")
        self.assertEqual(result, {"status": "available", "quantity": 3, "scope": "aggregate"})
        total = stock_status(self.product)
        self.assertEqual(total["status"], "available")
        self.assertEqual(total["quantity"], 10)

    def test_total_stock_does_not_confirm_specific_variant(self):
        product = {"name": "پوشاک", "stock": 30}
        self.assertEqual(stock_status(product, size="L", color="مشکی")["status"], "unverified")
        self.assertEqual(stock_status(product)["status"], "available")

    def test_bad_or_negative_quantities_are_unverified(self):
        product = {"name": "تی‌شرت", "sizes": ["L"], "colors": ["مشکی"],
                   "stock_by_variant": {"مشکی|L": -1}}
        self.assertEqual(stock_status(product, size="L", color="مشکی")["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
