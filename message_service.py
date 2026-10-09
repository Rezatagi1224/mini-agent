"""Channel-neutral entry point for customer conversations.

Web chat and Instagram should call this same service so business logic stays shared.
"""
from agent import run_agent


async def handle_customer_message(message: str, history: list | None = None) -> str:
    """Generate a customer-facing reply using the shared commercial agent."""
    return await run_agent(message, history if isinstance(history, list) else [])
