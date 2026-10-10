import json
import uuid
from pathlib import Path


from products import PRODUCTS as DEFAULT_PRODUCTS


DATA_FILE = Path("/data/products.json")


def _copy_products(items):
    return [dict(item) for item in items if isinstance(item, dict)]


def load_products():
    """Load the latest catalog from persistent Modal Volume, falling back to seed data."""
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return _copy_products(data)
        except (OSError, json.JSONDecodeError):
            pass
    return _copy_products(DEFAULT_PRODUCTS)


def save_products(products):
    """Validate the catalog shape, persist it, and commit the Modal Volume."""
    if not isinstance(products, list) or any(not isinstance(p, dict) for p in products):
        raise ValueError("کاتالوگ باید یک فهرست از محصولات باشد.")
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(products, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(DATA_FILE)


def normalize_product(payload, existing=None):
    if not isinstance(payload, dict):
        raise ValueError("اطلاعات محصول نامعتبر است.")

    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 160:
        raise ValueError("نام محصول الزامی است و باید کمتر از ۱۶۰ نویسه باشد.")

    try:
        price = int(str(payload.get("price", "")).replace(",", "").strip())
    except (TypeError, ValueError):
        raise ValueError("قیمت باید یک عدد صحیح به تومان باشد.")
    if price < 0:
        raise ValueError("قیمت نمی‌تواند منفی باشد.")

    cost_value = payload.get("cost_price", "")
    if cost_value not in (None, ""):
        try:
            cost_price = int(str(cost_value).replace(",", "").strip())
        except (TypeError, ValueError):
            raise ValueError("بهای خرید باید عدد صحیح به تومان باشد یا خالی بماند.")
        if cost_price < 0:
            raise ValueError("بهای خرید نمی‌تواند منفی باشد.")
    elif "cost_price" not in payload and existing and isinstance(existing.get("cost_price"), int):
        cost_price = existing["cost_price"]
    else:
        cost_price = None

    def list_field(key):
        value = payload.get(key, [])
        if isinstance(value, str):
            value = [part.strip() for part in value.replace("،", ",").split(",") if part.strip()]
        if not isinstance(value, list):
            raise ValueError(f"فیلد {key} باید فهرست باشد.")
        return [str(part).strip() for part in value if str(part).strip()][:100]

    product_id = str((existing or {}).get("id") or payload.get("id") or uuid.uuid4().hex[:12])
    sizes = list_field("sizes")
    colors = list_field("colors")
    product = {
        "id": product_id,
        "name": name,
        "category": str(payload.get("category", "")).strip()[:100],
        "description": str(payload.get("description", "")).strip()[:1000],
        "price": price,
        "currency": "تومان",
        "sizes": sizes,
        "colors": colors,
        "tags": list_field("tags"),
    }

    if cost_price is not None:
        product["cost_price"] = cost_price

    stock_value = payload.get("stock")
    if stock_value not in (None, ""):
        try:
            stock = int(str(stock_value).replace(",", "").strip())
        except (TypeError, ValueError):
            raise ValueError("موجودی باید عدد صحیح باشد یا خالی بماند.")
        if stock < 0:
            raise ValueError("موجودی نمی‌تواند منفی باشد.")
        product["stock"] = stock
    elif "stock" not in payload and existing and isinstance(existing.get("stock"), int):
        product["stock"] = existing["stock"]

    if "stock_by_variant" in payload:
        raw_map = payload.get("stock_by_variant")
        if raw_map is not None:
            if not isinstance(raw_map, dict):
                raise ValueError("موجودی سایز و رنگ باید به‌صورت جدول معتبر ارسال شود.")
            valid_keys = {f"{color}|{size}" for color in colors for size in sizes}
            variant_map = {}
            for key, value in raw_map.items():
                if key not in valid_keys:
                    raise ValueError("یکی از ترکیب‌های موجودی با سایز یا رنگ محصول مطابقت ندارد.")
                try:
                    stock = int(str(value).strip())
                except (TypeError, ValueError):
                    raise ValueError("موجودی هر ترکیب باید عدد صحیح باشد.")
                if stock < 0:
                    raise ValueError("موجودی هر ترکیب نمی‌تواند منفی باشد.")
                variant_map[key] = stock
            product["stock_by_variant"] = variant_map
    elif existing and isinstance(existing.get("stock_by_variant"), dict):
        product["stock_by_variant"] = existing["stock_by_variant"]

    return product
