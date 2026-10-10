"""Manual expense ledger for store-level profit reporting."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from store_context import resolve_data_file

DATA_FILE = Path("/data/expenses.json")


def _data_file():
    return resolve_data_file("expenses.json", DATA_FILE)


def load_expenses():
    if not _data_file().exists():
        return []
    try:
        data = json.loads(_data_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # Do not report a broken expense ledger as zero expenses.
        raise RuntimeError("فهرست هزینه‌ها قابل خواندن نیست؛ فایل داده را بررسی کن.") from exc
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise RuntimeError("ساختار فایل هزینه‌ها نامعتبر است؛ از نوشتن روی آن خودداری شد.")
    return data


def _save_expenses(expenses):
    _data_file().parent.mkdir(parents=True, exist_ok=True)
    temporary = _data_file().with_suffix(".tmp")
    temporary.write_text(json.dumps(expenses, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(_data_file())


def create_expense(payload):
    if not isinstance(payload, dict):
        raise ValueError("اطلاعات هزینه نامعتبر است.")
    description = str(payload.get("description", "")).strip()
    category = str(payload.get("category", "")).strip()
    if not description or len(description) > 160:
        raise ValueError("شرح هزینه الزامی است و حداکثر ۱۶۰ نویسه باشد.")
    if len(category) > 80:
        raise ValueError("دسته هزینه حداکثر ۸۰ نویسه باشد.")
    try:
        amount = int(str(payload.get("amount", "")).replace(",", "").strip())
    except (TypeError, ValueError):
        raise ValueError("مبلغ هزینه باید عدد صحیح به تومان باشد.")
    if amount <= 0:
        raise ValueError("مبلغ هزینه باید بیشتر از صفر باشد.")
    expenses = load_expenses()
    expense = {
        "id": "EXP-" + uuid.uuid4().hex[:10].upper(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "description": description,
        "category": category,
        "amount": amount,
        "currency": "تومان",
    }
    expenses.insert(0, expense)
    _save_expenses(expenses)
    return expense


def delete_expense(expense_id):
    expenses = load_expenses()
    remaining = [item for item in expenses if item.get("id") != expense_id]
    if len(remaining) == len(expenses):
        return False
    _save_expenses(remaining)
    return True
