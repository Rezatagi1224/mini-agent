import modal


image = modal.Image.debian_slim().pip_install(
    "fastapi[standard]",
    "openai"
)


app = modal.App("mini-agent")


secret = modal.Secret.from_name("openrouter-secret")


@app.function(
    image=image,
    secrets=[secret]
)
@modal.fastapi_endpoint(method="POST")
def chat(message: dict):

    from agent import run_agent

    user_message = message.get("message", "")

    return {
        "answer": run_agent(user_message)
    }

