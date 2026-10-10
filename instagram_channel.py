"""Instagram Messaging API helpers.

Configure the required META_* and INSTAGRAM_* secrets in Modal before enabling this
webhook. Never commit access tokens or app secrets to the repository.
"""
import hashlib
import hmac
import json
import os
from typing import Any

from store_context import validate_store_id



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


def resolve_instagram_account(account_id: str | None) -> dict[str, str] | None:
    """Resolve an inbound recipient account to its store and send credentials.

    Multi-account configuration uses INSTAGRAM_ACCOUNTS_JSON:
    {"meta_account_id": {"store_id": "shop_a", "access_token": "..."}}
    The per-account token is optional when INSTAGRAM_ACCESS_TOKEN is shared.
    Without that map, the legacy single-account variables route to the default
    store, preserving the existing installation.
    """
    raw = os.environ.get("INSTAGRAM_ACCOUNTS_JSON", "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("INSTAGRAM_ACCOUNTS_JSON must be valid JSON.") from exc
        if not isinstance(accounts, dict):
            raise RuntimeError("INSTAGRAM_ACCOUNTS_JSON must be a JSON object.")
        if not isinstance(account_id, str) or not account_id:
            return None
        record = accounts.get(account_id)
        if not isinstance(record, dict):
            return None
        try:
            store_id = validate_store_id(record.get("store_id"))
        except ValueError as exc:
            raise RuntimeError("Instagram account has an invalid store_id.") from exc
        token = record.get("access_token", os.environ.get("INSTAGRAM_ACCESS_TOKEN", ""))
        if not isinstance(token, str) or not token:
            return None
        return {"account_id": account_id, "store_id": store_id, "access_token": token}

    legacy_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    if not legacy_id or not token:
        return None
    if account_id and account_id != legacy_id:
        return None
    return {"account_id": legacy_id, "store_id": "default", "access_token": token}


def extract_text_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Extract customer-authored text DMs, ignoring echoes and non-text events."""
    messages: list[dict[str, str]] = []
    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            message = event.get("message") or {}
            sender = event.get("sender") or {}
            recipient = event.get("recipient") or {}
            sender_id = sender.get("id")
            account_id = recipient.get("id") or entry.get("id") or os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
            text = message.get("text")
            if message.get("is_echo"):
                continue
            if not isinstance(sender_id, str) or not sender_id:
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            messages.append({
                "sender_id": sender_id,
                "recipient_id": str(account_id) if account_id else "",
                "text": text.strip()[:6000],
                "message_id": str(message.get("mid", "")),
            })
    return messages


async def send_instagram_text(
    recipient_id: str,
    text: str,
    *,
    account_id: str | None = None,
    access_token: str | None = None,
) -> None:
    access_token = access_token or os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    instagram_account_id = account_id or os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    api_version = os.environ.get("META_GRAPH_API_VERSION", "v26.0")
    graph_base_url = os.environ.get("META_GRAPH_BASE_URL", "https://graph.instagram.com").rstrip("/")

    if not access_token or not instagram_account_id:
        raise RuntimeError(
            "Instagram messaging is not configured: set INSTAGRAM_ACCESS_TOKEN "
            "and INSTAGRAM_BUSINESS_ACCOUNT_ID in Modal secrets."
        )

    # Keep pure parsing/routing helpers importable in lightweight test environments.
    import httpx

    url = f"{graph_base_url}/{api_version}/{instagram_account_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text[:1000]},
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
