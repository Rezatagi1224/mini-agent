import modal

image = modal.Image.debian_slim().pip_install(
    "fastapi[standard]"
)

app = modal.App("mini-agent")


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def chat(message: dict):
    user_message = message.get("message", "")

    return {
        "answer": f"Agent received: {user_message}"
    }

