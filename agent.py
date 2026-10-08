
import os

from openai import AsyncOpenAI

from agents import (
    Agent,
    Runner,
    RunConfig,
    ModelSettings,
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
    model="inclusionai/ling-3.1-flash:free",
    openai_client=client,
)


model_settings = ModelSettings(
    extra_body={
        "models": [
            "openrouter/free",
        ]
    }
)


agent = Agent(
    name="Commercial Agent",
    instructions="""
    You are a professional commercial AI agent.

    Understand the user's request and use the
    previous conversation when relevant.

    Use the calculator tool when mathematical
    calculations are needed.

    Give clear and useful answers.
    Never claim a tool was executed if it was not.
    """,
    model=model,
    model_settings=model_settings,
    tools=[calculator],
)


async def run_agent(
    message: str,
    history: list,
) -> str:

    conversation = []

    for item in history[-12:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if (
            role in ("user", "assistant")
            and isinstance(content, str)
            and content.strip()
        ):
            conversation.append({
                "role": role,
                "content": content[:6000],
            })

    conversation.append({
        "role": "user",
        "content": message,
    })

    result = await Runner.run(
        agent,
        conversation,
        run_config=RunConfig(),
    )

    return result.final_output
