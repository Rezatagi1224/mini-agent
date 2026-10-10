import unittest
from datetime import datetime, timezone

from dashboard_analytics import build_dashboard


class DashboardAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    def test_status_counts_sales_daily_totals_and_repeat_customers(self):
        orders = [
            {"id": "1", "status": "pending", "phone": "۰۹۱۲-۳۴۵-۶۷۸۹", "total_price": 100, "quantity": 1,
             "product_name": "پیراهن", "created_at": "2026-10-10T09:00:00Z"},
            {"id": "2", "status": "confirmed", "phone": "0912 345 6789", "total_price": 200, "unit_cost": 100, "quantity": 2,
             "product_name": "پیراهن", "created_at": "2026-10-10T10:00:00Z"},
            {"id": "3", "status": "shipped", "payment_status": "paid", "phone": "+98 9123456789", "total_price": 300, "unit_cost": 50, "quantity": 3,
             "product_name": "پیراهن", "created_at": "2026-10-09T10:00:00Z"},
            {"id": "4", "status": "cancelled", "phone": "0935", "total_price": 50, "quantity": 1,
             "product_name": "تی‌شرت", "created_at": "2026-10-10T10:00:00Z"},
            {"id": "5", "status": "confirmed", "phone": "0988", "total_price": 700, "quantity": 1,
             "product_name": "کاپشن", "created_at": "2026-09-20T10:00:00Z"},
        ]
        result = build_dashboard(orders, [], now=self.now, expenses=[{"amount": 40}])
        self.assertEqual(result["orders"]["total"], 5)
        self.assertEqual(result["orders"]["pending"], 1)
        self.assertEqual(result["orders"]["confirmed"], 2)
        self.assertEqual(result["orders"]["shipped"], 1)
        self.assertEqual(result["orders"]["cancelled"], 1)
        self.assertEqual(result["orders"]["confirmed_and_shipped"], 3)
        self.assertEqual(result["sales"]["confirmed_amount"], 1200)
        self.assertEqual(result["sales"]["paid_amount"], 300)
        self.assertEqual(result["sales"]["outstanding_amount"], 900)
        self.assertEqual(result["sales"]["refunded_amount"], 0)
        self.assertEqual(result["sales"]["gross_profit_recorded"], 150)
        self.assertEqual(result["sales"]["recorded_expenses"], 40)
        self.assertEqual(result["sales"]["net_profit_recorded"], 110)
        self.assertEqual(result["sales"]["orders_missing_cost"], 1)
        self.assertFalse(result["sales"]["profit_complete"])
        self.assertEqual(result["sales"]["cancelled_amount"], 50)
        self.assertEqual(result["sales"]["last_7_days_amount"], 500)
        self.assertEqual(result["sales"]["average_order_amount"], 400)
        self.assertEqual(result["sales"]["cancellation_rate_percent"], 25)
        self.assertEqual(result["customers"]["repeat_customers"], 1)
        self.assertEqual(result["daily_sales"][-1], {"date": "2026-10-10", "amount": 200, "orders": 1})
        self.assertEqual(result["daily_sales"][-2], {"date": "2026-10-09", "amount": 300, "orders": 1})
        self.assertEqual(result["top_products"][0], {"name": "پیراهن", "quantity": 5})
        self.assertNotIn("phone", str(result))

    def test_inventory_alerts_distinguish_zero_low_and_unverified_variants(self):
        products = [
            {
                "name": "پیراهن",
                "sizes": ["L", "XL"],
                "colors": ["مشکی", "سفید"],
                "stock_by_variant": {"مشکی|L": 3, "مشکی|XL": 0, "سفید|L": 2},
            },
            {"name": "شلوار", "stock": 0},
            {"name": "تی‌شرت", "stock": 2},
        ]
        result = build_dashboard([], products, now=self.now, low_stock_threshold=3)
        inventory = result["inventory"]
        self.assertEqual(inventory["zero_variant_count"], 1)
        self.assertEqual(inventory["low_variant_count"], 2)
        self.assertEqual(inventory["unverified_variant_count"], 1)
        self.assertEqual(inventory["zero_product_count"], 1)
        self.assertEqual(inventory["low_product_count"], 1)
        self.assertTrue(any("موجودی صفر" in alert for alert in inventory["alerts"]))
        self.assertTrue(any("ثبت نشده" in alert for alert in inventory["alerts"]))

    def test_empty_and_unknown_orders_are_safe(self):
        result = build_dashboard([{"status": "unknown", "total_price": "bad"}], [], now=self.now)
        self.assertEqual(result["orders"]["total"], 1)
        self.assertEqual(result["sales"]["confirmed_amount"], 0)
        self.assertEqual(result["sales"]["cancellation_rate_percent"], 0)
        self.assertEqual(len(result["daily_sales"]), 7)


if __name__ == "__main__":
    unittest.main()
