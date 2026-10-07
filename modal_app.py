import modal
from fastapi import FastAPI
from fastapi.responses import FileResponse


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
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
        ""
    )

    answer = await run_agent(
        user_message
    )

    return {
        "answer": answer
    }


@app.function(
    image=image,
    secrets=[secret],
)
@modal.asgi_app()
def web():
    return web_app

