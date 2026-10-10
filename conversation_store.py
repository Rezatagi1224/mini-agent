"""Small server-side conversation history store with idle expiry.

Conversation identifiers are hashed before being used as filenames, so raw browser
session IDs are not written to disk. Only the latest 12 user/assistant messages are
retained for model context.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("CONVERSATION_DATA_DIR", "/conversation-data"))
MAX_MESSAGES = 12
MAX_CONTENT_CHARS = 6000
IDLE_TTL = timedelta(days=30)


def _now(value=None):
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _file_for(conversation_id):
    if not isinstance(conversation_id, str) or not conversation_id or len(conversation_id) > 200:
        raise ValueError("شناسه مکالمه نامعتبر است.")
    digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
    return DATA_DIR / (digest + ".json")


def _clean_history(history):
    if not isinstance(history, list):
        return []
    clean = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        clean.append({"role": role, "content": content[:MAX_CONTENT_CHARS]})
    return clean[-MAX_MESSAGES:]


def _is_expired(record, now=None):
    try:
        updated = datetime.fromisoformat(str(record.get("updated_at", "")))
    except (TypeError, ValueError):
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return _now(now) - updated.astimezone(timezone.utc) > IDLE_TTL


def load_history(conversation_id, now=None):
    """Load recent turns, deleting this conversation if it has been idle too long."""
    path = _file_for(conversation_id)
    if not path.exists():
        return []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or not isinstance(record.get("history"), list):
            path.unlink(missing_ok=True)
            return []
        if _is_expired(record, now=now):
            path.unlink(missing_ok=True)
            return []
        return _clean_history(record["history"])
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return []


def save_history(conversation_id, history, now=None):
    """Persist and return sanitized recent turns."""
    clean = _clean_history(history)
    path = _file_for(conversation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = _now(now).isoformat(timespec="seconds")
    record = {"updated_at": timestamp, "history": clean}
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return clean


MAX_SEEN_MESSAGE_IDS = 200
PROCESSING_LEASE = timedelta(minutes=3)


def _seen_file_for(conversation_id):
    return _file_for(conversation_id).with_suffix(".seen")


def _load_seen_record(path, now=None):
    if not path.exists():
        return {"updated_at": _now(now).isoformat(timespec="seconds"), "messages": {}}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return {"updated_at": _now(now).isoformat(timespec="seconds"), "messages": {}}
    if not isinstance(record, dict) or _is_expired(record, now=now):
        path.unlink(missing_ok=True)
        return {"updated_at": _now(now).isoformat(timespec="seconds"), "messages": {}}
    messages = record.get("messages")
    if not isinstance(messages, dict):
        messages = {}
    record["messages"] = messages
    return record


def _write_seen_record(path, record, now=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    record["updated_at"] = _now(now).isoformat(timespec="seconds")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def message_state(conversation_id, message_id, now=None):
    """Return new, processing, or done for an incoming platform message."""
    if not isinstance(message_id, str) or not message_id or len(message_id) > 500:
        return "new"
    record = _load_seen_record(_seen_file_for(conversation_id), now=now)
    item = record["messages"].get(message_id)
    if not isinstance(item, dict):
        return "new"
    if item.get("status") == "done":
        return "done"
    if item.get("status") == "processing":
        try:
            started = datetime.fromisoformat(str(item.get("updated_at", "")))
        except (TypeError, ValueError):
            return "new"
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if _now(now) - started.astimezone(timezone.utc) <= PROCESSING_LEASE:
            return "processing"
    return "new"


def claim_message(conversation_id, message_id, now=None):
    """Claim an inbound message unless it was handled or has a live processing lease."""
    if message_state(conversation_id, message_id, now=now) != "new":
        return False
    path = _seen_file_for(conversation_id)
    record = _load_seen_record(path, now=now)
    record["messages"][message_id] = {
        "status": "processing",
        "updated_at": _now(now).isoformat(timespec="seconds"),
    }
    # Bound the retry ledger so it does not grow indefinitely.
    if len(record["messages"]) > MAX_SEEN_MESSAGE_IDS:
        ordered = sorted(
            record["messages"].items(),
            key=lambda pair: str(pair[1].get("updated_at", "")) if isinstance(pair[1], dict) else "",
        )
        record["messages"] = dict(ordered[-MAX_SEEN_MESSAGE_IDS:])
    _write_seen_record(path, record, now=now)
    return True


def mark_message_processed(conversation_id, message_id, now=None):
    """Mark a successfully replied-to message as complete."""
    if not isinstance(message_id, str) or not message_id or len(message_id) > 500:
        return
    path = _seen_file_for(conversation_id)
    record = _load_seen_record(path, now=now)
    record["messages"][message_id] = {
        "status": "done",
        "updated_at": _now(now).isoformat(timespec="seconds"),
    }
    if len(record["messages"]) > MAX_SEEN_MESSAGE_IDS:
        ordered = sorted(
            record["messages"].items(),
            key=lambda pair: str(pair[1].get("updated_at", "")) if isinstance(pair[1], dict) else "",
        )
        record["messages"] = dict(ordered[-MAX_SEEN_MESSAGE_IDS:])
    _write_seen_record(path, record, now=now)


def release_message(conversation_id, message_id, now=None):
    """Release a message after a transient processing failure so a webhook retry can handle it."""
    path = _seen_file_for(conversation_id)
    record = _load_seen_record(path, now=now)
    record["messages"].pop(message_id, None)
    if not record["messages"]:
        path.unlink(missing_ok=True)
        return
    _write_seen_record(path, record, now=now)


def prune_expired(now=None):
    """Remove expired conversation files; intended to run during normal app requests."""
    if not DATA_DIR.exists():
        return 0
    current = _now(now)
    removed = 0
    paths = list(DATA_DIR.glob("*.json")) + list(DATA_DIR.glob("*.seen"))
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or _is_expired(record, now=current):
                path.unlink(missing_ok=True)
                removed += 1
        except (OSError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            removed += 1
    return removed
