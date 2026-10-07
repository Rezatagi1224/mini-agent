import modal

image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
        "openai"
    ).add_local_python_source("agent")
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

    answer = run_agent(user_message)

    return {
        "answer": answer
    }
