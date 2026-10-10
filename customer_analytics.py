"""Customer directory aggregates derived from recorded orders; no external CRM required."""
import unicodedata


def _phone_key(value):
    digits = []
    for character in unicodedata.normalize("NFKC", str(value or "")):
        try:
            digits.append(str(unicodedata.digit(character)))
        except (TypeError, ValueError):
            continue
    normalized = "".join(digits)
    if normalized.startswith("0098") and len(normalized) == 14:
        normalized = "0" + normalized[4:]
    elif normalized.startswith("98") and len(normalized) == 12:
        normalized = "0" + normalized[2:]
    return normalized


def build_customer_directory(orders):
    """Group orders by normalized phone and summarize only recorded order facts."""
    grouped = {}
    for order in orders:
        if not isinstance(order, dict):
            continue
        phone = str(order.get("phone", "")).strip()
        normalized_phone = _phone_key(phone)
        key = normalized_phone or ("order:" + str(order.get("id", "")))
        created_at = str(order.get("created_at", ""))
        status = str(order.get("status", "pending"))

        if key not in grouped:
            grouped[key] = {
                "customer_name": str(order.get("customer_name", "مشتری بدون نام")),
                "phone": phone,
                "address": str(order.get("address", "")),
                "order_count": 0,
                "completed_order_count": 0,
                "total_spent": 0,
                "last_order_at": created_at,
                "last_order_status": status,
                "products": [],
            }

        customer = grouped[key]
        customer["order_count"] += 1
        if status in {"confirmed", "shipped"}:
            customer["completed_order_count"] += 1
            try:
                amount = int(order.get("total_price", 0))
                if amount >= 0:
                    customer["total_spent"] += amount
            except (TypeError, ValueError, OverflowError):
                pass

        if created_at >= customer["last_order_at"]:
            customer["last_order_at"] = created_at
            customer["last_order_status"] = status
            customer["customer_name"] = str(order.get("customer_name", customer["customer_name"]))
            customer["phone"] = phone or customer["phone"]
            customer["address"] = str(order.get("address", customer["address"]))

        product_name = str(order.get("product_name", "")).strip()
        if product_name and product_name not in customer["products"]:
            customer["products"].append(product_name)

    customers = list(grouped.values())
    customers.sort(key=lambda item: (item["last_order_at"], item["order_count"]), reverse=True)
    summary = {
        "total_customers": len(customers),
        "repeat_customers": sum(1 for item in customers if item["order_count"] >= 2),
        "customers_with_completed_orders": sum(1 for item in customers if item["completed_order_count"] > 0),
        "completed_order_revenue": sum(item["total_spent"] for item in customers),
    }
    return {"customers": customers, "summary": summary}
