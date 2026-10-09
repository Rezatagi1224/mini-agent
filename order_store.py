"""Persistent customer order storage for the Mini Agent store."""
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path("/data/orders.json")
PRODUCTS_FILE = Path("/data/products.json")
PHONE_RE = re.compile(r"^[+0-9()\-\s]{8,24}$")
STATUSES = {
    "pending": "در انتظار تأیید",
    "confirmed": "تأیید شده",
    "shipped": "ارسال شده",
    "cancelled": "لغو شده",
}


def _norm(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _variant_key(stock_map, color, size):
    """Return the stored key and stock for the requested color|size, if present."""
    target = f"{_norm(color)}|{_norm(size)}"
    for key, value in stock_map.items():
        if _norm(key) == target:
            return key, value
    return None, None


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


def _load_products_file():
    if not PRODUCTS_FILE.exists():
        return []
    try:
        data = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_products_file(products):
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = PRODUCTS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(PRODUCTS_FILE)


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
    variant_stock = None
    if isinstance(stock_map, dict):
        _, raw_stock = _variant_key(stock_map, color, size)
        if raw_stock is not None:
            try:
                variant_stock = int(raw_stock)
            except (TypeError, ValueError):
                variant_stock = None
        # Once per-variant inventory is enabled, never substitute total stock
        # for a missing or invalid variant record.
        if variant_stock is None:
            stock_check = "unverified"
        else:
            stock_check = "confirmed"
            if variant_stock < 0:
                raise ValueError("موجودی ثبت‌شده این سایز و رنگ نامعتبر است.")
            if quantity > variant_stock:
                raise ValueError(f"موجودی ثبت‌شده این سایز و رنگ کافی نیست؛ {variant_stock} عدد ثبت شده است.")
    else:
        total_stock = product.get("stock")
        stock_check = "unverified"
        if isinstance(total_stock, int) and not isinstance(total_stock, bool):
            if total_stock < 0:
                raise ValueError("موجودی کل ثبت‌شده نامعتبر است.")
            if quantity > total_stock:
                raise ValueError(f"موجودی ثبت‌شده کافی نیست؛ موجودی کل {total_stock} عدد است.")

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
        "stock_check": stock_check,
        "inventory_deducted": False,
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
    order = next((item for item in orders if item.get("id") == order_id), None)
    if order is None:
        return None
    old_status = order.get("status", "pending")
    if old_status == status:
        return order
    allowed_transitions = {
        "pending": {"confirmed", "cancelled"},
        "confirmed": {"shipped", "cancelled"},
        "shipped": set(),
        "cancelled": set(),
    }
    if status not in allowed_transitions.get(old_status, set()):
        raise ValueError("این تغییر وضعیت مجاز نیست؛ وضعیت سفارش از مسیر فعلی قابل تغییر نیست.")

    # Validate and prepare inventory changes before writing either file.
    products = _load_products_file()
    product = next((p for p in products if str(p.get("id", "")) == str(order.get("product_id", ""))), None)
    quantity = int(order.get("quantity", 0) or 0)
    variant_key = None
    variant_stock = None
    inventory_action = None

    if old_status == "pending" and status == "confirmed":
        if product is None:
            raise ValueError("محصول این سفارش در کاتالوگ پیدا نشد؛ ابتدا کاتالوگ را بررسی کن.")
        stock_map = product.get("stock_by_variant")
        if isinstance(stock_map, dict):
            variant_key, raw_stock = _variant_key(stock_map, order.get("color", ""), order.get("size", ""))
            if variant_key is None:
                raise ValueError("موجودی دقیق این رنگ و سایز ثبت نشده است. ابتدا از پنل محصولات موجودی این ترکیب را ثبت کن.")
            try:
                variant_stock = int(raw_stock)
            except (TypeError, ValueError):
                raise ValueError("موجودی این رنگ و سایز معتبر نیست؛ سفارش تأیید نشد.")
            if variant_stock < quantity:
                raise ValueError(f"موجودی کافی نیست؛ فقط {variant_stock} عدد برای این رنگ و سایز ثبت شده است.")
            inventory_action = "variant_deduct"
        else:
            total_stock = product.get("stock")
            if not isinstance(total_stock, int) or isinstance(total_stock, bool) or total_stock < quantity:
                raise ValueError("موجودی کل کافی یا ثبت‌شده نیست؛ سفارش تأیید نشد.")
            inventory_action = "total_deduct"

    elif old_status == "confirmed" and status == "cancelled" and order.get("inventory_deducted"):
        if product is None:
            raise ValueError("محصول برای بازگرداندن موجودی پیدا نشد؛ لغو انجام نشد.")
        stock_map = product.get("stock_by_variant")
        if isinstance(stock_map, dict):
            variant_key, raw_stock = _variant_key(stock_map, order.get("color", ""), order.get("size", ""))
            if variant_key is None:
                raise ValueError("ترکیب رنگ و سایز برای بازگرداندن موجودی پیدا نشد؛ لغو انجام نشد.")
            try:
                variant_stock = int(raw_stock)
            except (TypeError, ValueError):
                raise ValueError("موجودی فعلی نامعتبر است؛ لغو انجام نشد.")
            inventory_action = "variant_restore"
        else:
            total_stock = product.get("stock")
            if not isinstance(total_stock, int) or isinstance(total_stock, bool):
                raise ValueError("موجودی کل برای بازگرداندن موجودی معتبر نیست؛ لغو انجام نشد.")
            inventory_action = "total_restore"

    if inventory_action == "variant_deduct":
        product["stock_by_variant"][variant_key] = variant_stock - quantity
        order["inventory_deducted"] = True
        order["stock_check"] = "confirmed"
    elif inventory_action == "total_deduct":
        product["stock"] -= quantity
        order["inventory_deducted"] = True
    elif inventory_action == "variant_restore":
        product["stock_by_variant"][variant_key] = variant_stock + quantity
        order["inventory_deducted"] = False
    elif inventory_action == "total_restore":
        product["stock"] += quantity
        order["inventory_deducted"] = False

    order["status"] = status
    order["status_label"] = STATUSES[status]
    # Persist inventory and order state; caller commits the shared Modal Volume.
    if inventory_action:
        _save_products_file(products)
    save_orders(orders)
    return order
