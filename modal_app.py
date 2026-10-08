
import uuid

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

memory_volume = modal.Volume.from_name(
    "mini-agent-memory",
    create_if_missing=True,
)


@app.function(
    image=image,
    secrets=[secret],
    volumes={
        "/data": memory_volume,
    },
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
    async def chat(message: dict):

        from agent import run_agent

        user_message = message.get(
            "message",
            "",
        )

        session_id = message.get(
            "session_id",
        )

        if (
            not isinstance(user_message, str)
            or not user_message.strip()
        ):
            return {
                "answer": "لطفاً یک پیام وارد کن.",
            }

        if len(user_message) > 6000:
            return {
                "answer": "پیام بیش از حد طولانی است.",
            }

        if (
            not isinstance(session_id, str)
            or not session_id.strip()
            or len(session_id) > 100
        ):
            session_id = str(uuid.uuid4())

        try:
            memory_volume.reload()

            answer = await run_agent(
                user_message,
                session_id,
            )

            memory_volume.commit()

            return {
                "answer": answer,
                "session_id": session_id,
            }

        
        except Exception:
            import traceback

            traceback.print_exc()

            return {
        "answer": "خطای داخلی Agent؛ لاگ Modal را بررسی کن.",
        "session_id": session_id,
    }

            return {
                "answer": (
                    "در اجرای Agent خطایی رخ داد. "
                    "لطفاً دوباره تلاش کن."
                ),
                "session_id": session_id,
            }


    return web_app
