
import os

from openai import AsyncOpenAI

from agents import (
    Agent,
    Runner,
    SQLiteSession,
    SessionSettings,
    RunConfig,
    ModelSettings,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

from tools import calculator


# Disable tracing
set_tracing_disabled(True)


# OpenRouter client
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)


# Primary model
model = OpenAIChatCompletionsModel(
    model="inclusionai/ling-3.1-flash:free",
    openai_client=client,
)


# Automatic model fallback
model_settings = ModelSettings(
    extra_body={
        "models": [
            "openrouter/free",
        ]
    }
)


# Agent
agent = Agent(
    name="Commercial Agent",
    instructions="""
    You are a professional commercial AI agent.

    Understand the user's request.
    Use the calculator tool when mathematical
    calculations are needed.
    Give clear and useful answers.
    Never claim a tool was executed if it was not.
    """,
    model=model,
    model_settings=model_settings,
    tools=[calculator],
)


# Persistent conversation database
DB_PATH = "/data/conversations.db"


async def run_agent(
    message: str,
    session_id: str,
) -> str:

    session = SQLiteSession(
        session_id,
        DB_PATH,
    )

    try:
        result = await Runner.run(
            agent,
            message,
            session=session,
            run_config=RunConfig(
                session_settings=SessionSettings(
                    limit=12
                )
            ),
        )

        return result.final_output

    finally:
        session.close()
