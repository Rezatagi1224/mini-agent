from openai import OpenAI

client = OpenAI()


def run_agent(message: str) -> str:
    response = client.responses.create(
        model="gpt-5-mini",
        input=f"""
You are a small helpful AI agent.

User:
{message}

Answer briefly and clearly.
"""
    )

    return response.output_text

