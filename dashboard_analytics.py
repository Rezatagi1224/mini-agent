"""Pure sales and inventory analytics used by the admin dashboard."""
from datetime import datetime, timedelta, timezone

from customer_analytics import normalize_phone_key


SOLD_STATUSES = {"confirmed", "shipped"}
STATUS_ORDER = ("pending", "confirmed", "shipped", "cancelled")


def _integer(value, default=0):
    if isinstance(value, bool):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if result >= 0 else default


def _parse_datetime(value):
    try:
        result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _inventory_report(products, low_stock_threshold=3):
    from inventory_utils import stock_status

    zero_variants = 0
    low_variants = 0
    unverified_variants = 0
    zero_products = 0
    low_products = 0
    unverified_products = 0
    alerts = []

    for product in products:
        if not isinstance(product, dict):
            continue
        name = str(product.get("name") or "محصول بدون نام")
        sizes = product.get("sizes") if isinstance(product.get("sizes"), list) else []
        colors = product.get("colors") if isinstance(product.get("colors"), list) else []

        if sizes and colors:
            for color in colors:
                for size in sizes:
                    status = stock_status(product, size=size, color=color)
                    label = f"{name} | {color} | {size}"
                    if status["status"] == "out_of_stock":
                        zero_variants += 1
                        alerts.append((0, label + " — موجودی صفر"))
                    elif status["status"] == "available" and status["quantity"] <= low_stock_threshold:
                        low_variants += 1
                        alerts.append((1, label + f" — فقط {status['quantity']} عدد"))
                    elif status["status"] == "unverified":
                        unverified_variants += 1
                        alerts.append((2, label + " — موجودی ثبت نشده/قابل تأیید نیست"))
            continue

        status = stock_status(product)
        if status["status"] == "out_of_stock":
            zero_products += 1
            alerts.append((0, name + " — موجودی کل صفر"))
        elif status["status"] == "available" and status["quantity"] <= low_stock_threshold:
            low_products += 1
            alerts.append((1, name + f" — فقط {status['quantity']} عدد در موجودی کل"))
        elif status["status"] == "unverified":
            unverified_products += 1
            alerts.append((2, name + " — موجودی کل ثبت نشده/قابل تأیید نیست"))

    alerts.sort(key=lambda item: (item[0], item[1]))
    return {
        "low_stock_threshold": low_stock_threshold,
        "zero_variant_count": zero_variants,
        "low_variant_count": low_variants,
        "unverified_variant_count": unverified_variants,
        "zero_product_count": zero_products,
        "low_product_count": low_products,
        "unverified_product_count": unverified_products,
        "alerts": [item[1] for item in alerts[:20]],
    }


def build_dashboard(orders, products, now=None, low_stock_threshold=3, expenses=None):
    """Build dashboard aggregates without returning customer contact details."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    orders = [order for order in orders if isinstance(order, dict)]
    products = [product for product in products if isinstance(product, dict)]
    by_status = {status: 0 for status in STATUS_ORDER}
    sold_orders = []
    cancelled_orders = []
    top = {}
    daily_amount = {}
    customer_completed_orders = {}

    start_date = now.date() - timedelta(days=6)
    dates = [(start_date + timedelta(days=offset)).isoformat() for offset in range(7)]
    for day in dates:
        daily_amount[day] = {"amount": 0, "orders": 0}

    confirmed_amount = 0
    cancelled_amount = 0
    gross_profit_recorded = 0
    orders_missing_cost = 0
    paid_amount = 0
    outstanding_amount = 0
    refunded_amount = 0
    last_7_days_amount = 0
    for order in orders:
        status = order.get("status", "pending")
        if status in by_status:
            by_status[status] += 1
        amount = _integer(order.get("total_price"))
        quantity = _integer(order.get("quantity"))
        if status in SOLD_STATUSES:
            confirmed_amount += amount
            if order.get("payment_status", "unpaid") == "paid":
                paid_amount += amount
            else:
                outstanding_amount += amount
            sold_orders.append(order)
            unit_cost = order.get("unit_cost")
            if isinstance(unit_cost, (int, float)) and not isinstance(unit_cost, bool) and unit_cost >= 0:
                gross_profit_recorded += amount - int(unit_cost) * quantity
            else:
                orders_missing_cost += 1
            name = str(order.get("product_name") or "محصول بدون نام")
            top[name] = top.get(name, 0) + quantity
            phone = normalize_phone_key(order.get("phone", ""))
            if phone:
                customer_completed_orders[phone] = customer_completed_orders.get(phone, 0) + 1
            created = _parse_datetime(order.get("created_at"))
            if created and created.date().isoformat() in daily_amount:
                day = created.date().isoformat()
                daily_amount[day]["amount"] += amount
                daily_amount[day]["orders"] += 1
                last_7_days_amount += amount
        elif status == "cancelled":
            cancelled_amount += amount
            if order.get("payment_status") == "refunded":
                refunded_amount += amount
            cancelled_orders.append(order)

    settled = len(sold_orders) + len(cancelled_orders)
    cancellation_rate = round((len(cancelled_orders) / settled) * 100, 1) if settled else 0
    average_order_amount = round(confirmed_amount / len(sold_orders)) if sold_orders else 0
    expenses = [item for item in (expenses or []) if isinstance(item, dict)]
    recorded_expenses = sum(_integer(item.get("amount")) for item in expenses)
    net_profit_recorded = gross_profit_recorded - recorded_expenses

    return {
        "orders": {
            "total": len(orders),
            **by_status,
            "confirmed_and_shipped": len(sold_orders),
            "settled": settled,
        },
        "sales": {
            "confirmed_amount": confirmed_amount,
            "paid_amount": paid_amount,
            "outstanding_amount": outstanding_amount,
            "refunded_amount": refunded_amount,
            "cancelled_amount": cancelled_amount,
            "last_7_days_amount": last_7_days_amount,
            "average_order_amount": average_order_amount,
            "cancellation_rate_percent": cancellation_rate,
            "gross_profit_recorded": gross_profit_recorded,
            "recorded_expenses": recorded_expenses,
            "net_profit_recorded": net_profit_recorded,
            "orders_missing_cost": orders_missing_cost,
            "profit_complete": orders_missing_cost == 0,
        },
        "customers": {
            "repeat_customers": sum(count >= 2 for count in customer_completed_orders.values()),
        },
        "daily_sales": [
            {"date": day, "amount": daily_amount[day]["amount"], "orders": daily_amount[day]["orders"]}
            for day in dates
        ],
        "top_products": [
            {"name": name, "quantity": quantity}
            for name, quantity in sorted(top.items(), key=lambda item: (-item[1], item[0]))[:5]
        ],
        "inventory": _inventory_report(products, low_stock_threshold=low_stock_threshold),
    }
