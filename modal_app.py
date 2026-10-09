import json

import modal


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source(
        "agent",
        "tools",
        "products",
        "message_service",
        "instagram_channel",
    )
    .add_local_dir("frontend", "/root/frontend")
)


app = modal.App("mini-agent")
secret = modal.Secret.from_name("openrouter-secret")


@app.function(image=image, secrets=[secret])
@modal.asgi_app()
def web():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, PlainTextResponse

    web_app = FastAPI()

    @web_app.get("/")
    async def home():
        return FileResponse("/root/frontend/index.html")

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
