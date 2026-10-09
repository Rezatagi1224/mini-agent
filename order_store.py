"""Persistent customer order storage for the Mini Agent store."""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path("/data/orders.json")
PHONE_RE = re.compile(r"^[+0-9()\-\s]{8,24}$")
STATUSES = {
    "pending": "در انتظار تأیید",
    "confirmed": "تأیید شده",
    "shipped": "ارسال شده",
    "cancelled": "لغو شده",
}


def load_orders():
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_orders(orders):
    if not isinstance(orders, list) or any(not isinstance(item, dict) for item in orders):
        raise ValueError("فهرست سفارش‌ها نامعتبر است.")
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(DATA_FILE)


def create_order(*, customer_name, phone, address, product, size, color, quantity):
    customer_name = str(customer_name or "").strip()
    phone = str(phone or "").strip()
    address = str(address or "").strip()
    size = str(size or "").strip()
    color = str(color or "").strip()
    if not customer_name or len(customer_name) > 120:
        raise ValueError("نام مشتری الزامی است.")
    if not PHONE_RE.fullmatch(phone):
        raise ValueError("شماره تماس معتبر نیست؛ فقط شماره تماس مشتری را ثبت کن.")
    if not address or len(address) < 8 or len(address) > 600:
        raise ValueError("آدرس ارسال کامل لازم است.")
    if not size or len(size) > 40:
        raise ValueError("سایز محصول الزامی است.")
    if not color or len(color) > 60:
        raise ValueError("رنگ محصول الزامی است.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("تعداد باید عدد صحیح باشد.")
    if quantity < 1 or quantity > 20:
        raise ValueError("تعداد سفارش باید بین ۱ تا ۲۰ باشد.")

    price = product.get("price")
    if not isinstance(price, (int, float)) or price < 0:
        raise ValueError("قیمت تأییدشده محصول ثبت نشده؛ سفارش ساخته نشد.")
    stock_map = product.get("stock_by_variant")
    known_stock = None
    if isinstance(stock_map, dict):
        for key in (f"{color}|{size}", f"{size}|{color}"):
            if key in stock_map:
                try:
                    known_stock = int(stock_map[key])
                except (TypeError, ValueError):
                    known_stock = None
                break
    if known_stock is None and isinstance(product.get("stock"), int):
        known_stock = product["stock"]
    if known_stock is not None and quantity > known_stock:
        raise ValueError(f"موجودی ثبت‌شده کافی نیست؛ موجودی فعلی {known_stock} عدد است.")

    order = {
        "id": "ORD-" + uuid.uuid4().hex[:8].upper(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "pending",
        "status_label": STATUSES["pending"],
        "customer_name": customer_name,
        "phone": phone,
        "address": address,
        "product_id": str(product.get("id", "")),
        "product_name": str(product.get("name", "")),
        "size": size,
        "color": color,
        "quantity": quantity,
        "unit_price": int(price),
        "total_price": int(price) * quantity,
        "currency": product.get("currency", "تومان"),
        "stock_check": "confirmed" if known_stock is not None else "unverified",
        "payment_status": "unpaid",
    }
    orders = load_orders()
    orders.insert(0, order)
    save_orders(orders)
    return order


def update_order_status(order_id, status):
    if status not in STATUSES:
        raise ValueError("وضعیت سفارش نامعتبر است.")
    orders = load_orders()
    for order in orders:
        if order.get("id") == order_id:
            order["status"] = status
            order["status_label"] = STATUSES[status]
            save_orders(orders)
            return order
    return None
