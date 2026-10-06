
from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent

app = FastAPI()


class Message(BaseModel):
    message: str


@app.post("/chat")
def chat(data: Message):
    answer = run_agent(data.message)

    return {
        "answer": answer
    }

