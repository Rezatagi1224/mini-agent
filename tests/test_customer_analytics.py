import unittest

from customer_analytics import build_customer_directory


class CustomerAnalyticsTests(unittest.TestCase):
    def test_groups_phone_formats_and_counts_only_completed_order_revenue(self):
        orders = [
            {
                "id": "3", "customer_name": "علی", "phone": "0912 345 6789",
                "address": "آدرس قدیمی", "status": "pending", "total_price": 900,
                "product_name": "تی‌شرت", "created_at": "2026-10-01T10:00:00+00:00",
            },
            {
                "id": "2", "customer_name": "علی رضایی", "phone": "۰۹۱۲-۳۴۵-۶۷۸۹",
                "address": "آدرس جدید", "status": "confirmed", "total_price": 500,
                "product_name": "شلوار", "created_at": "2026-10-03T10:00:00+00:00",
            },
            {
                "id": "1", "customer_name": "علی", "phone": "+98 9123456789",
                "address": "آدرس قبلی", "status": "cancelled", "total_price": 700,
                "product_name": "تی‌شرت", "created_at": "2026-10-02T10:00:00+00:00",
            },
        ]
        result = build_customer_directory(orders)
        self.assertEqual(result["summary"]["total_customers"], 1)
        customer = result["customers"][0]
        self.assertEqual(customer["order_count"], 3)
        self.assertEqual(customer["completed_order_count"], 1)
        self.assertEqual(customer["total_spent"], 500)
        self.assertEqual(customer["address"], "آدرس جدید")
        self.assertEqual(customer["last_order_status"], "confirmed")
        self.assertIn("شلوار", customer["products"])
        self.assertEqual(result["summary"]["completed_order_revenue"], 500)

    def test_missing_phone_does_not_merge_unrelated_customers(self):
        orders = [
            {"id": "a", "customer_name": "اول", "phone": "", "status": "pending", "created_at": "2026-10-01"},
            {"id": "b", "customer_name": "دوم", "phone": "", "status": "pending", "created_at": "2026-10-02"},
        ]
        result = build_customer_directory(orders)
        self.assertEqual(result["summary"]["total_customers"], 2)
        self.assertEqual(result["summary"]["repeat_customers"], 0)

    def test_malformed_orders_are_ignored_and_bad_amount_is_safe(self):
        result = build_customer_directory([
            None,
            {"id": "a", "phone": "0912", "status": "shipped", "total_price": "bad", "created_at": ""},
        ])
        self.assertEqual(result["summary"]["total_customers"], 1)
        self.assertEqual(result["summary"]["completed_order_revenue"], 0)


if __name__ == "__main__":
    unittest.main()
