import os
from openai import OpenAI


def run_agent(message: str) -> str:

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"]
    )

    response = client.chat.completions.create(
        model="nvidia/nemotron-3-ultra-550b-a55b:free",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful AI agent. Answer clearly and concisely."
            },
            {
                "role": "user",
                "content": message
            }
        ]
    )

    return response.choices[0].message.content

