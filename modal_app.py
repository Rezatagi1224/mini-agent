import json
import os

import modal


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source(
        "agent",
        "tools",
        "products",
        "product_store",
        "message_service",
        "instagram_channel",
    )
    .add_local_dir("frontend", "/root/frontend")
)


app = modal.App("mini-agent")
secret = modal.Secret.from_name("openrouter-secret")
product_volume = modal.Volume.from_name("mini-agent-data", create_if_missing=True)


@app.function(
    image=image,
    secrets=[secret],
    volumes={"/data": product_volume},
)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, PlainTextResponse

    web_app = FastAPI()

    @web_app.get("/")
    async def home():
        return FileResponse("/root/frontend/index.html")

    @web_app.get("/admin")
    async def admin_page():
        return FileResponse("/root/frontend/admin.html")

    def require_admin(request: Request):
        import hmac
        expected = os.environ.get("ADMIN_PASSWORD", "")
        supplied = request.headers.get("x-admin-password", "")
        if not expected:
            raise HTTPException(
                status_code=503,
                detail="رمز مدیریت تنظیم نشده است. ADMIN_PASSWORD را در Secret با نام openrouter-secret ثبت کن.",
            )
        if not supplied or not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="رمز مدیریت نادرست است.")

    @web_app.get("/admin/products")
    async def admin_list_products(request: Request):
        require_admin(request)
        product_volume.reload()
        from product_store import load_products
        return {"products": load_products()}

    @web_app.post("/admin/products")
    async def admin_create_product(request: Request, body: dict):
        require_admin(request)
        product_volume.reload()
        product_volume.reload()
        from product_store import load_products, save_products, normalize_product
        products = load_products()
        product = normalize_product(body)
        if any(p.get("id") == product["id"] for p in products):
            raise HTTPException(status_code=409, detail="شناسه محصول تکراری است.")
        products.append(product)
        save_products(products)
        product_volume.commit()
        return {"ok": True, "product": product}

    @web_app.put("/admin/products/{product_id}")
    async def admin_update_product(product_id: str, request: Request, body: dict):
        require_admin(request)
        from product_store import load_products, save_products, normalize_product
        products = load_products()
        for index, current in enumerate(products):
            if current.get("id") == product_id:
                products[index] = normalize_product(body, existing=current)
                save_products(products)
                product_volume.commit()
                return {"ok": True, "product": products[index]}
        raise HTTPException(status_code=404, detail="محصول پیدا نشد.")

    @web_app.delete("/admin/products/{product_id}")
    async def admin_delete_product(product_id: str, request: Request):
        require_admin(request)
        product_volume.reload()
        from product_store import load_products, save_products
        products = load_products()
        remaining = [p for p in products if p.get("id") != product_id]
        if len(remaining) == len(products):
            raise HTTPException(status_code=404, detail="محصول پیدا نشد.")
        save_products(remaining)
        product_volume.commit()
        return {"ok": True}

    @web_app.get("/style.css")
    async def style():
        return FileResponse("/root/frontend/style.css")

    @web_app.get("/app.js")
    async def javascript():
        return FileResponse("/root/frontend/app.js")

    @web_app.post("/chat")
    async def chat(body: dict):
        from message_service import handle_customer_message

        message = body.get("message", "")
        history = body.get("history", [])

        if not isinstance(message, str) or not message.strip():
            return {"answer": "لطفاً یک پیام وارد کن."}
        if len(message) > 6000:
            return {"answer": "پیام بیش از حد طولانی است."}
        if not isinstance(history, list):
            history = []

        try:
            product_volume.reload()
            answer = await handle_customer_message(message.strip(), history)
            return {"answer": answer}
        except Exception:
            import traceback
            traceback.print_exc()
            return {"answer": "اجرای Agent با خطا مواجه شد. لاگ Modal را بررسی کن."}

    @web_app.get("/webhooks/instagram")
    async def verify_instagram_webhook(request: Request):
        from instagram_channel import verify_webhook_challenge

        mode = request.query_params.get("hub.mode", "")
        token = request.query_params.get("hub.verify_token", "")
        challenge = request.query_params.get("hub.challenge", "")
        verified = verify_webhook_challenge(mode, token, challenge)
        if verified is None:
            raise HTTPException(status_code=403, detail="Webhook verification failed")
        return PlainTextResponse(verified)

    @web_app.post("/webhooks/instagram")
    async def instagram_webhook(request: Request):
        from instagram_channel import (
            extract_text_messages,
            send_instagram_text,
            verify_webhook_signature,
        )
        from message_service import handle_customer_message

        raw_body = await request.body()
        signature = request.headers.get("x-hub-signature-256")
        if not verify_webhook_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        if not isinstance(payload, dict) or payload.get("object") != "instagram":
            return {"status": "ignored"}

        # Initial integration scaffold: text DMs only.
        # Add persistent conversation history and event-id deduplication before
        # relying on this for production sales.
        for incoming in extract_text_messages(payload):
            answer = await handle_customer_message(incoming["text"], history=[])
            await send_instagram_text(incoming["sender_id"], answer)

        return {"status": "received"}

    return web_app
