"""Tenant-aware filesystem paths for isolated store data.

The legacy/default store keeps its existing /data/*.json paths. Named stores
use /data/stores/<store_id>/*.json. The active store is held in a ContextVar so
concurrent async requests do not share a mutable global tenant selection.
"""
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
import re
from typing import Iterator

DATA_ROOT = Path("/data")
DEFAULT_STORE_ID = "default"
_STORE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_current_store_id: ContextVar[str] = ContextVar(
    "mini_agent_store_id", default=DEFAULT_STORE_ID
)


def validate_store_id(store_id: object) -> str:
    if not isinstance(store_id, str) or not _STORE_ID_RE.fullmatch(store_id):
        raise ValueError("شناسه فروشگاه نامعتبر است.")
    return store_id


def current_store_id() -> str:
    return _current_store_id.get()


@contextmanager
def use_store(store_id: str) -> Iterator[None]:
    """Temporarily select a validated store for the current async context."""
    validated = validate_store_id(store_id)
    token: Token = _current_store_id.set(validated)
    try:
        yield
    finally:
        _current_store_id.reset(token)


def resolve_data_file(filename: str, legacy_path: Path) -> Path:
    """Resolve a known data filename within the active store's directory."""
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ValueError("نام فایل داده نامعتبر است.")
    store_id = current_store_id()
    if store_id == DEFAULT_STORE_ID:
        return Path(legacy_path)
    return DATA_ROOT / "stores" / store_id / filename
