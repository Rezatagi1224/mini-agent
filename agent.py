import os
from memory import build_messages
from openai import AsyncOpenAI

from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

from tools import calculator


set_tracing_disabled(True)


client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)


model = OpenAIChatCompletionsModel(
    model="nvidia/nemotron-3-ultra-550b-a55b:free",
    openai_client=client,
)


agent = Agent(
    name="Commercial Agent",

    instructions="""
    You are a professional commercial AI agent.

    Your job is to understand the user's request,
    decide whether a tool is necessary,
    use the appropriate tool when needed,
    and then provide a clear final answer.

    Available tools:
    - calculator: for mathematical calculations.

    Never pretend that a tool was executed when it was not.
    """,

    model=model,

    tools=[
        calculator
    ],
)


async def run_agent(message: str, history=None) -> str:
    messages = build_messages(
        history or [],
        message,
    )

    result = await Runner.run(
        agent,
        input=messages,
    )

    return result.final_output

