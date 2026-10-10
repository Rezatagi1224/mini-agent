import unicodedata

from agents import function_tool
from product_store import load_products
from order_store import create_order
from inventory_utils import stock_status, stock_message


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
    currency = product.get("currency", "تومان")
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
        category: Product category.
        size: Requested size.
        color: Requested color.
        max_results: Maximum number of results, from 1 to 10.
    """
    products = load_products()
    if not products:
        return "کاتالوگ محصول هنوز خالی است؛ ابتدا محصولات واقعی فروشگاه را در پنل ثبت کن."
    max_results = max(1, min(int(max_results), 10))
    matches = []
    for product in products:
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
        inventory = stock_message(p, size=size, color=color)
        lines.append(
            f"- {p.get('name', 'نامشخص')} | شناسه: {p.get('id', 'ثبت نشده')} | "
            f"دسته: {p.get('category', 'ثبت نشده')} | قیمت: {_format_price(p)} | "
            f"سایزها: {', '.join(map(str, p.get('sizes', []))) or 'ثبت نشده'} | "
            f"رنگ‌ها: {', '.join(map(str, p.get('colors', []))) or 'ثبت نشده'} | {inventory}"
        )
    return "\n".join(lines)


@function_tool
def check_stock(product_name: str, size: str = "", color: str = "") -> str:
    """Check stock without assuming total product stock proves variant availability."""
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
        names = "، ".join(str(p.get("name", "نامشخص")) for p in matches[:5])
        return f"چند محصول پیدا شد ({names}). لطفاً نام دقیق‌تر یا شناسه محصول را بده."
    return stock_message(matches[0], size=size, color=color)


@function_tool
def recommend_products(occasion: str = "", budget: float = 0, size: str = "", style: str = "", color: str = "") -> str:
    """Recommend products with soft relevance ranking and strict size/color/budget constraints.

    Args:
        occasion: Occasion, such as everyday, work, or party.
        budget: Maximum budget in the catalog currency; 0 means no budget filter.
        size: Requested size.
        style: Desired style, such as boxy, casual, or classic.
        color: Preferred color.
    """
    products = load_products()
    if not products:
        return "برای پیشنهاد واقعی، ابتدا محصولات و مشخصات تأییدشده را در پنل ثبت کن."

    def relevance(text, preference):
        preference = _normalize(preference)
        text = _normalize(text)
        if not preference:
            return 0
        if preference in text:
            return 3
        tokens = [token for token in preference.split() if len(token) > 1]
        return sum(1 for token in tokens if token in text)

    matches = []
    for product in products:
        if not isinstance(product, dict):
            continue
        # Size, color, and budget are hard constraints; style and occasion
        # are ranking signals because catalog descriptions may use synonyms.
        if size and not any(_normalize(size) == _normalize(s) for s in product.get("sizes", [])):
            continue
        if color and not any(_normalize(color) == _normalize(c) for c in product.get("colors", [])):
            continue
        price = product.get("price")
        if budget > 0 and (
            not isinstance(price, (int, float)) or isinstance(price, bool)
            or price < 0 or price > budget
        ):
            continue

        inventory = stock_status(product, size=size, color=color)
        if inventory["status"] == "out_of_stock":
            continue

        searchable = " ".join([
            _product_text(product),
            str(product.get("occasion", "")),
            str(product.get("fit", "")),
            str(product.get("style", "")),
        ])
        score = relevance(searchable, occasion) + relevance(searchable, style)
        matches.append((product, inventory, score))

    if not matches:
        return ("محصولی با موجودی قابل استفاده و مطابق محدودیت‌های سایز، رنگ و بودجه پیدا نشد. "
                "می‌توانی یکی از این محدودیت‌ها را تغییر بدهی؛ موجودی ثبت‌نشده باید توسط فروشگاه بررسی شود.")

    has_soft_preferences = bool(occasion.strip() or style.strip())
    relevant_matches = [item for item in matches if item[2] > 0]
    note = ""
    if has_soft_preferences and relevant_matches:
        matches = relevant_matches
    elif has_soft_preferences:
        note = "تطابق دقیق با سبک یا مناسبت در اطلاعات کاتالوگ پیدا نشد؛ گزینه‌های زیر فقط با محدودیت‌های ثبت‌شده سازگارند. "

    matches.sort(key=lambda item: (
        item[1]["status"] != "available",
        -item[2],
        -(item[1]["quantity"] or 0),
        str(item[0].get("name", "")),
    ))
    results = [
        f"- {product.get('name', 'نامشخص')} | قیمت: {_format_price(product)} | "
        f"سایزها: {', '.join(map(str, product.get('sizes', []))) or 'ثبت نشده'} | "
        f"رنگ‌ها: {', '.join(map(str, product.get('colors', []))) or 'ثبت نشده'} | "
        f"{stock_message(product, size=size, color=color, status=inventory)}"
        for product, inventory, _score in matches[:5]
    ]
    return note + "\n".join(results)


@function_tool
def submit_customer_order(
    customer_name: str,
    phone: str,
    address: str,
    product_name: str,
    size: str,
    color: str,
    quantity: int = 1,
    customer_confirmed: bool = False,
) -> str:
    """Create a pending order only after the customer explicitly confirms they want to place it and provides all required details.

    Args:
        customer_name: Customer's full name.
        phone: Customer's contact phone number.
        address: Complete shipping address.
        product_name: Exact product name or product ID from the store catalog.
        size: Requested size.
        color: Requested color.
        quantity: Number of items requested.
        customer_confirmed: True only when the customer explicitly confirms order submission after seeing the item, variant, quantity, price, and total.
    """
    if customer_confirmed is not True:
        return "برای ثبت سفارش، ابتدا نام کالا، سایز، رنگ، تعداد، قیمت و مبلغ کل را به مشتری اعلام کن و صریحاً تأیید بگیر."
    matches = [
        p for p in load_products()
        if isinstance(p, dict) and (
            _normalize(product_name) == _normalize(p.get("id", ""))
            or _normalize(product_name) == _normalize(p.get("name", ""))
        )
    ]
    if len(matches) != 1:
        return "محصول با نام دقیق در کاتالوگ پیدا نشد یا نام مبهم است؛ سفارش ثبت نشد."
    product = matches[0]
    if not product.get("sizes"):
        return "سایزهای این محصول در کاتالوگ ثبت نشده؛ سفارش ثبت نشد. ابتدا مشخصات محصول را در پنل کامل کن."
    if not any(_normalize(size) == _normalize(s) for s in product["sizes"]):
        return "این سایز در مشخصات ثبت‌شده محصول نیست؛ سفارش ثبت نشد."
    if not product.get("colors"):
        return "رنگ‌های این محصول در کاتالوگ ثبت نشده؛ سفارش ثبت نشد. ابتدا مشخصات محصول را در پنل کامل کن."
    if not any(_normalize(color) == _normalize(c) for c in product["colors"]):
        return "این رنگ در مشخصات ثبت‌شده محصول نیست؛ سفارش ثبت نشد."
    try:
        order = create_order(
            customer_name=customer_name,
            phone=phone,
            address=address,
            product=product,
            size=size,
            color=color,
            quantity=quantity,
        )
    except ValueError as error:
        return f"سفارش ثبت نشد: {error}"
    stock_note = "موجودی ثبت‌شده بررسی شد." if order["stock_check"] == "confirmed" else "موجودی سایز و رنگ هنوز باید توسط فروشگاه تأیید شود."
    return (
        f"سفارش با موفقیت ثبت شد و در انتظار تأیید فروشگاه است. "
        f"شماره سفارش: {order['id']} | محصول: {order['product_name']} | "
        f"سایز: {order['size']} | رنگ: {order['color']} | تعداد: {order['quantity']} | "
        f"مبلغ کل: {order['total_price']:,} تومان. {stock_note} "
        "این سفارش هنوز تأیید نهایی نشده و پرداختی انجام نشده است."
    )
