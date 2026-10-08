
import modal

image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source(
        "agent",
        "tools",
        "memory",
    )
    .add_local_dir(
        "frontend",
        "/root/frontend",
    )
)

app = modal.App("mini-agent")

secret = modal.Secret.from_name("openrouter-secret")


@app.function(
    image=image,
    secrets=[secret],
)
@modal.asgi_app()
def web():
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, HTMLResponse
    from pathlib import Path

    web_app = FastAPI()

    @web_app.get("/")
    async def home():
        html_path = Path("/root/frontend/index.html")

        if not html_path.exists():
            return HTMLResponse(
                "<h1>index.html not found</h1>",
                status_code=500,
            )

        return HTMLResponse(
            html_path.read_text(encoding="utf-8")
        )

    @web_app.get("/style.css")
    async def style():
        return FileResponse(
            "/root/frontend/style.css"
        )

    @web_app.get("/app.js")
    async def javascript():
        return FileResponse(
            "/root/frontend/app.js"
        )

    @web_app.post("/chat")
    async def chat(message: dict):
        from agent import run_agent

        user_message = message.get("message", "")
        history = message.get("history", [])

        if (
            not isinstance(user_message, str)
            or not user_message.strip()
        ):
            return {
                "answer": "لطفاً یک پیام وارد کن."
            }

        if len(user_message) > 6000:
            return {
                "answer": "پیام بیش از حد طولانی است."
            }

        if not isinstance(history, list):
            history = []

        answer = await run_agent(
            user_message,
            history,
        )

        return {"answer": answer}

    return web_app
