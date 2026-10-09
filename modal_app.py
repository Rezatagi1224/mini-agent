import json
import os

import modal


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("agent", "tools", "products", "product_store", "order_store", "message_service", "instagram_channel")
    .add_local_dir("frontend", "/root/frontend")
)

app = modal.App("mini-agent")
secret = modal.Secret.from_name("openrouter-secret")
product_volume = modal.Volume.from_name("mini-agent-data", create_if_missing=True)


@app.function(image=image, secrets=[secret], volumes={"/data": product_volume})
@modal.asgi_app()
def web():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse
    from product_store import load_products, save_products, normalize_product
    from order_store import load_orders, update_order_status

    web_app = FastAPI()

    @web_app.get("/")
    async def home():
        return FileResponse("/root/frontend/index.html")

    @web_app.get("/admin")
    async def admin():
        return FileResponse("/root/frontend/admin.html")

    @web_app.get("/admin/orders-page")
    async def orders_page():
        return FileResponse("/root/frontend/orders.html")

    @web_app.get("/admin/dashboard-page")
    async def dashboard_page():
        return FileResponse("/root/frontend/dashboard.html")

    def require_admin(request: Request):
        import hmac
        expected = os.environ.get("ADMIN_PASSWORD", "")
        if not expected or not hmac.compare_digest(request.headers.get("x-admin-password", ""), expected):
            raise HTTPException(status_code=401, detail="رمز مدیریت نادرست است.")

    def commit_volume():
        product_volume.commit()

    @web_app.get("/admin/products")
    async def get_products(request: Request):
        require_admin(request)
        product_volume.reload()
        return {"products": load_products()}

    @web_app.post("/admin/products")
    async def create_product(request: Request):
        require_admin(request)
        product_volume.reload()
        try:
            payload = await request.json()
            products = load_products()
            product = normalize_product(payload)
            products.append(product)
            save_products(products)
            commit_volume()
            return {"product": product}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @web_app.put("/admin/products/{product_id}")
    async def edit_product(product_id: str, request: Request):
        require_admin(request)
        product_volume.reload()
        try:
            payload = await request.json()
            products = load_products()
            index = next((i for i, item in enumerate(products) if str(item.get("id", "")) == product_id), None)
            if index is None:
                raise HTTPException(status_code=404, detail="محصول پیدا نشد.")
            products[index] = normalize_product(payload, existing=products[index])
            save_products(products)
            commit_volume()
            return {"product": products[index]}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @web_app.delete("/admin/products/{product_id}")
    async def remove_product(product_id: str, request: Request):
        require_admin(request)
        product_volume.reload()
        products = load_products()
        remaining = [item for item in products if str(item.get("id", "")) != product_id]
        if len(remaining) == len(products):
            raise HTTPException(status_code=404, detail="محصول پیدا نشد.")
        save_products(remaining)
        commit_volume()
        return {"ok": True}

    @web_app.get("/admin/orders")
    async def get_orders(request: Request):
        require_admin(request)
        product_volume.reload()
        return {"orders": load_orders()}

    @web_app.patch("/admin/orders/{order_id}")
    async def change_order_status(order_id: str, request: Request):
        require_admin(request)
        product_volume.reload()
        try:
            payload = await request.json()
            status = payload.get("status") if isinstance(payload, dict) else None
            order = update_order_status(order_id, status)
            if order is None:
                raise HTTPException(status_code=404, detail="سفارش پیدا نشد.")
            commit_volume()
            return {"order": order}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @web_app.get("/admin/dashboard")
    async def dashboard(request: Request):
        require_admin(request)
        product_volume.reload()
        orders = load_orders()
        confirmed = [o for o in orders if o.get("status") in ("confirmed", "shipped")]
        cancelled = [o for o in orders if o.get("status") == "cancelled"]
        top = {}
        for order in confirmed:
            name = order.get("product_name", "")
            top[name] = top.get(name, 0) + int(order.get("quantity", 0))
        return {
            "orders": {
                "total": len(orders),
                "pending": sum(o.get("status") == "pending" for o in orders),
                "confirmed": len(confirmed),
            },
            "sales": {
                "confirmed_amount": sum(o.get("total_price", 0) for o in confirmed),
                "cancelled_amount": sum(o.get("total_price", 0) for o in cancelled),
            },
            "top_products": [
                {"name": name, "quantity": quantity}
                for name, quantity in sorted(top.items(), key=lambda item: item[1], reverse=True)[:5]
            ],
        }

    @web_app.get("/style.css")
    async def style():
        return FileResponse("/root/frontend/style.css")

    return web_app
