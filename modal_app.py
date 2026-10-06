import modal

app = modal.App("mini-agent")


@app.function()
def test():
    return "Agent is running!"
