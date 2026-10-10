"""Conservative stock status helpers shared by sales tools and unit tests."""
import unicodedata


def _normalize(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    return " ".join(value.split())


def _parse_quantity(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _expected_variants(product):
    colors = product.get("colors", [])
    sizes = product.get("sizes", [])
    if not isinstance(colors, list) or not isinstance(sizes, list):
        return []
    return [
        (_normalize(color), _normalize(size))
        for color in colors
        for size in sizes
        if _normalize(color) and _normalize(size)
    ]


def stock_status(product, size="", color=""):
    """Return available, out_of_stock, or unverified without guessing variant stock."""
    size_norm = _normalize(size)
    color_norm = _normalize(color)
    stock_map = product.get("stock_by_variant")

    if isinstance(stock_map, dict):
        entries = {}
        for key, value in stock_map.items():
            if not isinstance(key, str) or "|" not in key:
                continue
            key_color, key_size = key.split("|", 1)
            pair = (_normalize(key_color), _normalize(key_size))
            if pair[0] and pair[1]:
                entries[pair] = value

        if size_norm and color_norm:
            pair = (color_norm, size_norm)
            if pair not in entries:
                return {"status": "unverified", "quantity": None, "scope": "variant"}
            quantity = _parse_quantity(entries[pair])
            if quantity is None:
                return {"status": "unverified", "quantity": None, "scope": "variant"}
            return {"status": "available" if quantity > 0 else "out_of_stock",
                    "quantity": quantity, "scope": "variant"}

        expected = _expected_variants(product)
        if not expected:
            return {"status": "unverified", "quantity": None, "scope": "aggregate"}
        relevant = [
            pair for pair in expected
            if (not color_norm or pair[0] == color_norm)
            and (not size_norm or pair[1] == size_norm)
        ]
        if not relevant or any(pair not in entries for pair in relevant):
            return {"status": "unverified", "quantity": None, "scope": "aggregate"}
        quantities = [_parse_quantity(entries[pair]) for pair in relevant]
        if any(quantity is None for quantity in quantities):
            return {"status": "unverified", "quantity": None, "scope": "aggregate"}
        total = sum(quantities)
        return {"status": "available" if total > 0 else "out_of_stock",
                "quantity": total, "scope": "aggregate"}

    # Total stock cannot prove that a specific size or color is in stock.
    if size_norm or color_norm:
        return {"status": "unverified", "quantity": None, "scope": "variant"}
    quantity = _parse_quantity(product.get("stock"))
    if quantity is None:
        return {"status": "unverified", "quantity": None, "scope": "total"}
    return {"status": "available" if quantity > 0 else "out_of_stock",
            "quantity": quantity, "scope": "total"}


def stock_message(product, size="", color="", status=None):
    """Format a Persian inventory statement using recorded data only."""
    result = status or stock_status(product, size=size, color=color)
    name = str(product.get("name", "این محصول"))
    if size and color:
        variant = f"رنگ {color} و سایز {size}"
    elif size:
        variant = f"سایز {size}"
    elif color:
        variant = f"رنگ {color}"
    else:
        variant = "تمام محصول"
    if result["status"] == "unverified":
        return (f"موجودی {name} برای {variant} کامل و دقیق ثبت نشده است؛ "
                "موجود یا ناموجود بودن قابل تأیید نیست و فروشگاه باید بررسی کند.")
    quantity = int(result["quantity"])
    if result["scope"] == "variant":
        return f"موجودی ثبت‌شده {name} برای {variant}: {quantity} عدد."
    if result["scope"] == "aggregate":
        return f"مجموع موجودی ثبت‌شده {name} برای {variant}: {quantity} عدد."
    if result["status"] == "out_of_stock":
        return f"موجودی کل ثبت‌شده {name}: صفر عدد."
    return f"موجودی کل ثبت‌شده {name}: {quantity} عدد؛ این عدد موجودی یک سایز یا رنگ خاص را تأیید نمی‌کند."
