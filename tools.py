import json
import unicodedata

from agents import function_tool
from product_store import load_products


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    return " ".join(value.split())


def _contains(haystack: str, needle: str) -> bool:
    needle = _normalize(needle)
    return not needle or needle in _normalize(haystack)


def _product_text(product: dict) -> str:
    return " ".join([
        str(product.get("name", "")),
        str(product.get("category", "")),
        str(product.get("description", "")),
        " ".join(map(str, product.get("tags", []))),
    ])


def _format_price(product: dict) -> str:
    price = product.get("price")
    if not isinstance(price, (int, float)) or price < 0:
        return "قیمت ثبت نشده"
    currency = product.get("currency", "IRR")
    return f"{price:,.0f} {currency}"


@function_tool
def calculator(a: float, b: float, operation: str) -> str:
    """Perform basic arithmetic.

    Args:
        a: First number.
        b: Second number.
        operation: One of add, subtract, multiply, or divide.
    """
    operations = {
        "add": lambda: a + b,
        "subtract": lambda: a - b,
        "multiply": lambda: a * b,
        "divide": lambda: a / b if b != 0 else None,
    }

    operation = _normalize(operation)
    if operation not in operations:
        return "عملیات نامعتبر است. از add، subtract، multiply یا divide استفاده کن."
    if operation == "divide" and b == 0:
        return "خطا: تقسیم بر صفر تعریف نشده است."
    return str(operations[operation]())


@function_tool
def search_products(
    query: str = "",
    category: str = "",
    size: str = "",
    color: str = "",
    max_results: int = 5,
) -> str:
    """Search the verified store catalog by product name, category, size, and color.

    Args:
        query: Words to search in product name, description, or tags.
        category: Product category, such as T-shirt or jeans.
        size: Requested size.
        color: Requested color.
        max_results: Maximum number of results, from 1 to 10.
    """
    if not load_products():
        return "کاتالوگ محصول هنوز خالی است؛ ابتدا محصولات واقعی فروشگاه را در products.py ثبت کن."

    max_results = max(1, min(int(max_results), 10))
    matches = []
    for product in load_products():
        if not isinstance(product, dict):
            continue
        if not _contains(_product_text(product), query):
            continue
        if not _contains(product.get("category", ""), category):
            continue
        if size and not any(_normalize(size) == _normalize(s) for s in product.get("sizes", [])):
            continue
        if color and not any(_normalize(color) in _normalize(c) for c in product.get("colors", [])):
            continue
        matches.append(product)

    if not matches:
        return "محصولی مطابق فیلترهای واردشده در کاتالوگ پیدا نشد."

    lines = []
    for p in matches[:max_results]:
        lines.append(
            f"- {p.get('name', 'نامشخص')} | شناسه: {p.get('id', 'ثبت نشده')} | "
            f"دسته: {p.get('category', 'ثبت نشده')} | قیمت: {_format_price(p)} | "
            f"سایزها: {', '.join(map(str, p.get('sizes', []))) or 'ثبت نشده'} | "
            f"رنگ‌ها: {', '.join(map(str, p.get('colors', []))) or 'ثبت نشده'}"
        )
    return "\n".join(lines)


@function_tool
def check_stock(
    product_name: str,
    size: str = "",
    color: str = "",
) -> str:
    """Check recorded stock for a product and optional size and color.

    Args:
        product_name: Product name or exact product ID.
        size: Requested size, if relevant.
        color: Requested color, if relevant.
    """
    matches = [
        p for p in load_products()
        if isinstance(p, dict) and (
            _normalize(product_name) == _normalize(p.get("id", ""))
            or _normalize(product_name) == _normalize(p.get("name", ""))
            or _contains(p.get("name", ""), product_name)
        )
    ]

    if not matches:
        return "این محصول در کاتالوگ ثبت نشده؛ موجودی آن قابل تأیید نیست."
    if len(matches) > 1:
        names = ", ".join(str(p.get("name", "نامشخص")) for p in matches[:5])
        return f"چند محصول پیدا شد ({names}). لطفاً نام دقیق‌تر یا شناسه محصول را بده."

    product = matches[0]
    stock_map = product.get("stock_by_variant")
    if not isinstance(stock_map, dict):
        stock_map = {}

    if size and color:
        keys = [f"{color}|{size}", f"{size}|{color}"]
    elif size:
        keys = [size] + [k for k in stock_map if _normalize(k).endswith("|" + _normalize(size))]
    elif color:
        keys = [color] + [k for k in stock_map if _normalize(k).startswith(_normalize(color) + "|")]
    else:
        total = product.get("stock")
        if isinstance(total, (int, float)) and total >= 0:
            return f"موجودی ثبت‌شده {product.get('name')}: {total:g} عدد."
        return "موجودی کل این محصول ثبت نشده است؛ عددی برای موجودی نمی‌توان تأیید کرد."

    for key in keys:
        if key in stock_map and isinstance(stock_map[key], (int, float)) and stock_map[key] >= 0:
            variant = "، ".join(x for x in [color, size] if x)
            return f"موجودی ثبت‌شده {product.get('name')} ({variant or key}): {stock_map[key]:g} عدد."

    variant = "، ".join(x for x in [color, size] if x)
    return f"موجودی {product.get('name')} برای {variant or 'این محصول'} در داده‌ها ثبت نشده است؛ موجود یا ناموجود بودن قابل تأیید نیست."


@function_tool
def recommend_products(
    occasion: str = "",
    budget: float = 0,
    size: str = "",
    style: str = "",
    color: str = "",
) -> str:
    """Recommend catalog products matching a customer's needs using recorded data only.

    Args:
        occasion: Occasion, such as everyday, work, or party.
        budget: Maximum budget in the catalog currency; 0 means no budget filter.
        size: Requested size.
        style: Desired style, such as boxy, casual, or classic.
        color: Preferred color.
    """
    if not PRODUCTS:
        return "برای پیشنهاد واقعی، ابتدا محصولات و مشخصات تأییدشده را در products.py ثبت کن."

    matches = []
    for product in PRODUCTS:
        if not isinstance(product, dict):
            continue
        searchable = _product_text(product) + " " + str(product.get("occasion", ""))
        if occasion and not _contains(searchable, occasion):
            continue
        if style and not _contains(searchable, style):
            continue
        if size and not any(_normalize(size) == _normalize(s) for s in product.get("sizes", [])):
            continue
        if color and not any(_normalize(color) in _normalize(c) for c in product.get("colors", [])):
            continue
        price = product.get("price")
        if budget > 0 and (
            not isinstance(price, (int, float)) or price < 0 or price > budget
        ):
            continue
        matches.append(product)

    if not matches:
        return "محصول ثبت‌شده‌ای با تمام شرایط درخواستی پیدا نشد. می‌توانی یکی از فیلترها را تغییر بدهی."

    matches.sort(key=lambda p: (not bool(p.get("stock_by_variant") or p.get("stock") is not None), str(p.get("name", ""))))
    lines = []
    for p in matches[:5]:
        lines.append(
            f"- {p.get('name', 'نامشخص')} | قیمت: {_format_price(p)} | "
            f"سایزها: {', '.join(map(str, p.get('sizes', []))) or 'ثبت نشده'} | "
            f"رنگ‌ها: {', '.join(map(str, p.get('colors', []))) or 'ثبت نشده'}"
        )
    return "\n".join(lines)
