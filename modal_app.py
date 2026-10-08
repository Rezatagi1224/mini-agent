
import modal


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements(
        "requirements.txt"
    )
    .add_local_python_source(
        "agent",
        "tools",
    )
    .add_local_dir(
        "frontend",
        "/root/frontend",
    )
)


app = modal.App("mini-agent")

secret = modal.Secret.from_name(
    "openrouter-secret"
)


@app.function(
    image=image,
    secrets=[secret],
)
@modal.asgi_app()
def web():

    from fastapi import FastAPI
    from fastapi.responses import FileResponse

    web_app = FastAPI()

    @web_app.get("/")
    async def home():
        return FileResponse(
            "/root/frontend/index.html"
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
    async def chat(body: dict):

        from agent import run_agent

        message = body.get("message", "")
        history = body.get("history", [])

        if (
            not isinstance(message, str)
            or not message.strip()
        ):
            return {
                "answer": "لطفاً یک پیام وارد کن."
            }

        if len(message) > 6000:
            return {
                "answer": "پیام بیش از حد طولانی است."
            }

        if not isinstance(history, list):
            history = []

        try:
            print("HISTORY RECEIVED:")
            print(history)
            answer = await run_agent(
                message.strip(),
                history,
            )

            return {
                "answer": answer,
            }

        except Exception:
            import traceback

            traceback.print_exc()

            return {
                "answer": (
                    "اجرای Agent با خطا مواجه شد. "
                    "لاگ Modal را بررسی کن."
                )
            }

    return web_app
