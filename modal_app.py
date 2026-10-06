import modal

app = modal.App("mini-agent")


@app.function()
@modal.fastapi_endpoint(method="POST")
def chat(message: dict):
    user_message = message.get("message", "")

    return {
        "answer": f"Agent received: {user_message}"
    }
