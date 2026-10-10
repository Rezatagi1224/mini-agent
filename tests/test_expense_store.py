import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import expense_store


class ExpenseStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "expenses.json"
        self.patch = patch.object(expense_store, "DATA_FILE", self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_create_and_delete_expense(self):
        expense = expense_store.create_expense({
            "description": "هزینه بسته‌بندی",
            "category": "بسته‌بندی",
            "amount": "125000",
        })
        self.assertEqual(expense["amount"], 125000)
        self.assertEqual(expense["currency"], "تومان")
        self.assertEqual(expense_store.load_expenses()[0]["id"], expense["id"])
        self.assertTrue(expense_store.delete_expense(expense["id"]))
        self.assertEqual(expense_store.load_expenses(), [])
        self.assertFalse(expense_store.delete_expense(expense["id"]))

    def test_invalid_expenses_are_rejected(self):
        for payload in [
            {"description": "", "amount": 100},
            {"description": "هزینه", "amount": 0},
            {"description": "هزینه", "amount": -5},
            {"description": "هزینه", "amount": "نامعتبر"},
        ]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    expense_store.create_expense(payload)

    def test_corrupt_file_is_safe(self):
        self.path.write_text("{bad json", encoding="utf-8")
        self.assertEqual(expense_store.load_expenses(), [])


if __name__ == "__main__":
    unittest.main()
