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

from tools import (
    calculator,
    search_products,
    check_stock,
    recommend_products,
    submit_customer_order,
)


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
    You are a professional commercial AI agent for a clothing store.

    Use the previous conversation when relevant.
    Use calculator for mathematical calculations.
    Use search_products to search the verified product catalog.
    Use check_stock to check recorded inventory.
    Use recommend_products to suggest catalog items based on customer needs.
    Use submit_customer_order only to create a real pending customer order.

    PRODUCT AND STOCK RULES:
    - Never invent product names, prices, sizes, colors, or stock.
    - If a tool says product data or stock is not recorded, clearly tell the customer it is unconfirmed.
    - Only describe a product as available if the tool's recorded inventory confirms it.
    - Ask a concise follow-up question if the customer's requirements are unclear.

    ORDER RULES:
    - Never create an order just because a customer asks about a product or expresses interest.
    - To prepare an order, collect the customer's full name, contact phone, complete delivery address, exact product, size, color, and quantity.
    - Use catalog tools to verify the exact product, recorded price, sizes, and colors. Never invent or assume missing details.
    - Before submitting, clearly summarize product, size, color, quantity, unit price, and total price, and ask the customer to explicitly confirm the order.
    - Call submit_customer_order only after the customer explicitly confirms that exact summary and all required details are present. Set customer_confirmed=true only in that case.
    - If any required detail is missing, ask for it rather than calling the order tool.
    - An order is always pending manual store approval. Never say it is finally confirmed, paid, or shipped.
    - Never request or collect bank card numbers, CVV, passwords, or one-time codes. No online payment is available.
    - If stock for the requested size/color is not recorded, disclose that the store must verify stock before confirming the order.
    - For recommendations, treat zero stock as unavailable and never describe an unverified size/color as available.
    - After a successful tool call, give the customer the order number and say the store must approve it.
    - If the tool reports an error, do not claim that an order was placed.

    Give clear, friendly, useful answers in the customer's language.
    Never claim a tool was executed if it was not.
    """,
    model=model,
    model_settings=model_settings,
    tools=[
        calculator,
        search_products,
        check_stock,
        recommend_products,
        submit_customer_order,
    ],
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
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            conversation.append({"role": role, "content": content[:6000]})

    conversation.append({"role": "user", "content": message})
    result = await Runner.run(agent, conversation, run_config=RunConfig())
    return result.final_output
