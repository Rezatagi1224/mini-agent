"""Instagram Messaging API helpers.

Configure the required META_* and INSTAGRAM_* secrets in Modal before enabling this
webhook. Never commit access tokens or app secrets to the repository.
"""
import hashlib
import hmac
import os
from typing import Any

import httpx


def verify_webhook_challenge(mode: str, verify_token: str, challenge: str) -> str | None:
    expected = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "")
    if mode == "subscribe" and expected and hmac.compare_digest(verify_token, expected):
        return challenge
    return None


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    app_secret = os.environ.get("META_APP_SECRET", "")
    if not app_secret or not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("sha256=" + digest, signature)


def extract_text_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Extract customer-authored text DMs, ignoring echoes and non-text events."""
    messages: list[dict[str, str]] = []
    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            message = event.get("message") or {}
            sender = event.get("sender") or {}
            sender_id = sender.get("id")
            text = message.get("text")
            if message.get("is_echo"):
                continue
            if not isinstance(sender_id, str) or not sender_id:
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            messages.append({
                "sender_id": sender_id,
                "text": text.strip()[:6000],
                "message_id": str(message.get("mid", "")),
            })
    return messages


async def send_instagram_text(recipient_id: str, text: str) -> None:
    access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    instagram_account_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    api_version = os.environ.get("META_GRAPH_API_VERSION", "v26.0")
    graph_base_url = os.environ.get("META_GRAPH_BASE_URL", "https://graph.instagram.com").rstrip("/")

    if not access_token or not instagram_account_id:
        raise RuntimeError(
            "Instagram messaging is not configured: set INSTAGRAM_ACCESS_TOKEN "
            "and INSTAGRAM_BUSINESS_ACCOUNT_ID in Modal secrets."
        )

    url = f"{graph_base_url}/{api_version}/{instagram_account_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text[:1000]},
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
