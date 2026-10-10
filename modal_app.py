import json
import os

import modal


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("agent", "tools", "products", "product_store", "order_store", "expense_store", "message_service", "instagram_channel", "conversation_store", "inventory_utils", "dashboard_analytics", "customer_analytics", "admin_auth", "store_context")
    .add_local_dir("frontend", "/root/frontend")
)

app = modal.App("mini-agent")
secret = modal.Secret.from_name("openrouter-secret")
product_volume = modal.Volume.from_name("mini-agent-data", create_if_missing=True)
conversation_volume = modal.Volume.from_name("mini-agent-conversation-data", create_if_missing=True)


@app.function(
    image=image,
    secrets=[secret],
    volumes={"/data": product_volume, "/conversation-data": conversation_volume},
)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.responses import FileResponse, PlainTextResponse
    from uuid import UUID
    import asyncio
    from product_store import load_products, save_products, normalize_product
    from order_store import load_orders, update_order_status, update_order_payment_status
    from dashboard_analytics import build_dashboard
    from expense_store import load_expenses, create_expense, delete_expense
    from customer_analytics import build_customer_directory
    from admin_auth import (
        ADMIN_SESSION_COOKIE,
        ADMIN_SESSION_TTL_SECONDS,
        AdminLoginRateLimiter,
        create_admin_session_token,
        verify_admin_password,
        verify_admin_session_token,
    )
    from message_service import handle_customer_message
    from conversation_store import (
        load_history, save_history, prune_expired,
        claim_message, mark_message_processed, release_message,
    )
    from instagram_channel import (
        verify_webhook_challenge, verify_webhook_signature,
        extract_text_messages, send_instagram_text,
    )

    web_app = FastAPI()
    conversation_locks = {}
    admin_login_limiter = AdminLoginRateLimiter(max_attempts=5, window_seconds=15 * 60)

    def web_conversation_key(value):
        if not isinstance(value, str):
            raise HTTPException(status_code=400, detail="شناسه مکالمه نامعتبر است.")
        try:
            parsed = UUID(value)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(status_code=400, detail="شناسه مکالمه نامعتبر است.")
        if str(parsed) != value.lower():
            raise HTTPException(status_code=400, detail="شناسه مکالمه نامعتبر است.")
        return "web:" + str(parsed)

    @web_app.get("/chat/history")
    async def chat_history(conversation_id: str):
        key = web_conversation_key(conversation_id)
        conversation_volume.reload()
        removed = prune_expired()
        history = load_history(key)
        if removed:
            conversation_volume.commit()
        return {"history": history}

    @web_app.post("/chat")
    async def chat(request: Request):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="درخواست نامعتبر است.")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="درخواست نامعتبر است.")

        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise HTTPException(status_code=400, detail="پیام خالی است.")
        message = message.strip()
        if len(message) > 6000:
            raise HTTPException(status_code=400, detail="پیام نمی‌تواند بیشتر از ۶۰۰۰ نویسه باشد.")

        key = web_conversation_key(payload.get("conversation_id"))
        lock = conversation_locks.setdefault(key, asyncio.Lock())
        async with lock:
            conversation_volume.reload()
            product_volume.reload()
            prune_expired()
            history = load_history(key)
            try:
                answer = await handle_customer_message(message, history)
                # Order tools write to /data; commit the product volume so orders
                # created by the agent survive container changes and later requests.
                product_volume.commit()
            except Exception:
                raise HTTPException(
                    status_code=502,
                    detail="فعلاً ارتباط با Agent برقرار نشد. دوباره تلاش کن.",
                )

            saved_history = save_history(
                key,
                history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": answer},
                ],
            )
            conversation_volume.commit()
            return {"answer": answer, "history": saved_history}

    @web_app.get("/webhooks/instagram")
    async def verify_instagram_webhook(request: Request):
        params = request.query_params
        challenge = verify_webhook_challenge(
            params.get("hub.mode", ""),
            params.get("hub.verify_token", ""),
            params.get("hub.challenge", ""),
        )
        if challenge is None:
            raise HTTPException(status_code=403, detail="تأیید وب‌هوک اینستاگرام ناموفق بود.")
        return PlainTextResponse(challenge)

    @web_app.post("/webhooks/instagram")
    async def receive_instagram_webhook(request: Request):
        raw_body = await request.body()
        signature = request.headers.get("x-hub-signature-256")
        if not verify_webhook_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="امضای وب‌هوک معتبر نیست.")

        try:
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="محتوای وب‌هوک نامعتبر است.")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="محتوای وب‌هوک نامعتبر است.")

        messages = extract_text_messages(payload)
        processed = 0
        for item in messages:
            sender_id = item.get("sender_id", "")
            message_id = item.get("message_id", "")
            text = item.get("text", "").strip()
            # Meta message IDs are required for safe retry/deduplication.
            if not sender_id or not message_id or not text:
                continue

            key = "instagram:" + sender_id
            lock = conversation_locks.setdefault(key, asyncio.Lock())
            async with lock:
                conversation_volume.reload()
                product_volume.reload()
                removed = prune_expired()
                if not claim_message(key, message_id):
                    if removed:
                        conversation_volume.commit()
                    continue

                # Persist a short processing lease before invoking the model so that
                # webhook retries do not trigger simultaneous duplicate replies.
                conversation_volume.commit()
                try:
                    history = load_history(key)
                    answer = await handle_customer_message(text, history)
                    # The agent may have created an order in /data. Persist it before
                    # attempting the outbound reply to avoid losing a successful order.
                    product_volume.commit()
                    save_history(
                        key,
                        history + [
                            {"role": "user", "content": text},
                            {"role": "assistant", "content": answer},
                        ],
                    )
                    mark_message_processed(key, message_id)
                    conversation_volume.commit()
                except Exception:
                    # Failures before the order/reply result is committed can be retried.
                    release_message(key, message_id)
                    conversation_volume.commit()
                    raise HTTPException(
                        status_code=502,
                        detail="پردازش پیام اینستاگرام ناموفق بود؛ ارسال‌کننده می‌تواند دوباره تلاش کند.",
                    )
                try:
                    await send_instagram_text(sender_id, answer)
                    processed += 1
                except Exception:
                    # The message is already marked done. Do not re-run the agent and
                    # accidentally create a duplicate order just because sending failed.
                    raise HTTPException(
                        status_code=502,
                        detail="سفارش/پیام پردازش و ذخیره شد، اما ارسال پاسخ ناموفق بود.",
                    )

        return {"ok": True, "processed": processed}

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

    @web_app.get("/admin/customers-page")
    async def customers_page():
        return FileResponse("/root/frontend/customers.html")

    @web_app.post("/admin/login")
    async def admin_login(request: Request, response: Response):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="درخواست ورود نامعتبر است.")
        password = payload.get("password") if isinstance(payload, dict) else None
        expected = os.environ.get("ADMIN_PASSWORD", "")
        client_key = request.client.host if request.client else "unknown"
        if not admin_login_limiter.is_allowed(client_key):
            retry_after = admin_login_limiter.retry_after(client_key)
            raise HTTPException(
                status_code=429,
                detail="به‌دلیل تلاش‌های ناموفق زیاد، ورود موقتاً محدود شده است.",
                headers={"Retry-After": str(retry_after)},
            )
        if not verify_admin_password(password, expected):
            admin_login_limiter.record_failure(client_key)
            raise HTTPException(status_code=401, detail="رمز مدیریت نادرست است.")

        admin_login_limiter.clear(client_key)
        token = create_admin_session_token(expected)
        response.set_cookie(
            key=ADMIN_SESSION_COOKIE,
            value=token,
            max_age=ADMIN_SESSION_TTL_SECONDS,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/admin",
        )
        return {"ok": True, "expires_in": ADMIN_SESSION_TTL_SECONDS}

    @web_app.post("/admin/logout")
    async def admin_logout(response: Response):
        response.delete_cookie(
            key=ADMIN_SESSION_COOKIE,
            path="/admin",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        return {"ok": True}

    def require_admin(request: Request):
        expected = os.environ.get("ADMIN_PASSWORD", "")
        token = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not verify_admin_session_token(token, expected):
            raise HTTPException(status_code=401, detail="نشست مدیریت معتبر نیست؛ دوباره وارد شو.")

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

    @web_app.patch("/admin/orders/{order_id}/payment")
    async def change_order_payment_status(order_id: str, request: Request):
        require_admin(request)
        product_volume.reload()
        try:
            payload = await request.json()
            payment_status = payload.get("payment_status") if isinstance(payload, dict) else None
            order = update_order_payment_status(order_id, payment_status)
            if order is None:
                raise HTTPException(status_code=404, detail="سفارش پیدا نشد.")
            commit_volume()
            return {"order": order}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @web_app.get("/admin/expenses")
    async def get_expenses(request: Request):
        require_admin(request)
        product_volume.reload()
        return {"expenses": load_expenses()}

    @web_app.post("/admin/expenses")
    async def add_expense(request: Request):
        require_admin(request)
        product_volume.reload()
        try:
            payload = await request.json()
            expense = create_expense(payload)
            commit_volume()
            return {"expense": expense}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @web_app.delete("/admin/expenses/{expense_id}")
    async def remove_expense(expense_id: str, request: Request):
        require_admin(request)
        product_volume.reload()
        if not delete_expense(expense_id):
            raise HTTPException(status_code=404, detail="هزینه پیدا نشد.")
        commit_volume()
        return {"ok": True}

    @web_app.get("/admin/dashboard")
    async def dashboard(request: Request):
        require_admin(request)
        product_volume.reload()
        return build_dashboard(load_orders(), load_products(), expenses=load_expenses())

    @web_app.get("/admin/customers")
    async def customers(request: Request):
        require_admin(request)
        product_volume.reload()
        return build_customer_directory(load_orders())

    @web_app.get("/app.js")
    async def app_js():
        return FileResponse("/root/frontend/app.js", media_type="application/javascript")

    @web_app.get("/style.css")
    async def style():
        return FileResponse("/root/frontend/style.css")

    return web_app
