"""Persistent store registry and store-administrator credential management.

The registry lives outside individual tenant directories. Passwords are salted,
PBKDF2-HMAC-SHA256 hashes; raw store-admin passwords are never persisted.
"""
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from store_context import validate_store_id

REGISTRY_FILE = Path("/data/stores/registry.json")
PASSWORD_ITERATIONS = 310_000
MIN_PASSWORD_LENGTH = 12


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_registry():
    if not REGISTRY_FILE.exists():
        return {"version": 1, "stores": {}}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("فهرست فروشگاه‌ها قابل خواندن نیست؛ از نوشتن روی آن خودداری شد.") from exc
    if (
        not isinstance(data, dict)
        or data.get("version") != 1
        or not isinstance(data.get("stores"), dict)
    ):
        raise RuntimeError("ساختار فهرست فروشگاه‌ها نامعتبر است؛ فایل داده را بررسی کن.")
    for store_id, record in data["stores"].items():
        try:
            validate_store_id(store_id)
        except ValueError as exc:
            raise RuntimeError("شناسه‌ای نامعتبر در فهرست فروشگاه‌ها ثبت شده است.") from exc
        if not isinstance(record, dict) or not isinstance(record.get("active"), bool):
            raise RuntimeError("رکوردی نامعتبر در فهرست فروشگاه‌ها وجود دارد.")
    return data


def _write_registry(registry):
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = REGISTRY_FILE.with_name(REGISTRY_FILE.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(REGISTRY_FILE)
    finally:
        temporary.unlink(missing_ok=True)


def _hash_password(password, salt=None, iterations=PASSWORD_ITERATIONS):
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"رمز مدیر فروشگاه باید دست‌کم {MIN_PASSWORD_LENGTH} نویسه باشد.")
    salt_bytes = secrets.token_bytes(16) if salt is None else salt
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return {
        "salt": salt_bytes.hex(),
        "password_hash": digest.hex(),
        "iterations": iterations,
    }


def _public_record(store_id, record):
    return {
        "store_id": store_id,
        "name": record.get("name", store_id),
        "active": bool(record.get("active", False)),
        "created_at": record.get("created_at"),
    }


def list_stores(*, include_inactive=True):
    registry = _read_registry()
    records = [
        _public_record(store_id, record)
        for store_id, record in registry["stores"].items()
        if include_inactive or record.get("active") is True
    ]
    return sorted(records, key=lambda record: (record["store_id"] != "default", record["store_id"]))


def get_store(store_id, *, include_inactive=True):
    try:
        validate_store_id(store_id)
    except ValueError:
        return None
    if store_id == "default":
        return {"store_id": "default", "name": "فروشگاه اصلی", "active": True, "created_at": None}
    record = _read_registry()["stores"].get(store_id)
    if not isinstance(record, dict):
        return None
    if not include_inactive and record.get("active") is not True:
        return None
    return _public_record(store_id, record)


def is_store_active(store_id):
    if store_id == "default":
        return True
    record = get_store(store_id, include_inactive=True)
    return bool(record and record.get("active") is True)


def verify_store_password(store_id, password):
    """Authenticate only active, explicitly registered named stores."""
    if store_id == "default" or not isinstance(password, str):
        return False
    record = _read_registry()["stores"].get(store_id)
    if not isinstance(record, dict) or record.get("active") is not True:
        return False
    try:
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["password_hash"])
        iterations = int(record["iterations"])
        if len(salt) != 16 or len(expected) != 32 or not 100_000 <= iterations <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def create_store(store_id, name, password):
    store_id = validate_store_id(store_id)
    if store_id == "default":
        raise ValueError("شناسه default رزرو شده است.")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise ValueError("نام فروشگاه باید بین ۱ تا ۱۰۰ نویسه باشد.")
    credentials = _hash_password(password)
    registry = _read_registry()
    if store_id in registry["stores"]:
        raise ValueError("این شناسه فروشگاه قبلاً ثبت شده است.")
    registry["stores"][store_id] = {
        "name": name.strip(),
        "active": True,
        "created_at": _now(),
        **credentials,
    }
    _write_registry(registry)
    return _public_record(store_id, registry["stores"][store_id])


def reset_store_password(store_id, password):
    store_id = validate_store_id(store_id)
    if store_id == "default":
        raise ValueError("رمز فروشگاه اصلی از تنظیم ADMIN_PASSWORD مدیریت می‌شود.")
    registry = _read_registry()
    record = registry["stores"].get(store_id)
    if not isinstance(record, dict):
        raise ValueError("فروشگاه پیدا نشد.")
    record.update(_hash_password(password))
    _write_registry(registry)
    return _public_record(store_id, record)


def set_store_active(store_id, active):
    store_id = validate_store_id(store_id)
    if store_id == "default":
        raise ValueError("فروشگاه اصلی را نمی‌توان غیرفعال کرد.")
    if not isinstance(active, bool):
        raise ValueError("وضعیت فعال بودن باید مشخص باشد.")
    registry = _read_registry()
    record = registry["stores"].get(store_id)
    if not isinstance(record, dict):
        raise ValueError("فروشگاه پیدا نشد.")
    record["active"] = active
    _write_registry(registry)
    return _public_record(store_id, record)
