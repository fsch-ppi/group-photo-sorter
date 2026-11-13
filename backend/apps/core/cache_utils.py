"""
Resilient Redis cache and distributed lock utilities.

Provides:
- Safe wrappers around Django's cache backend that never crash on transient
  Redis connection issues.
- Atomic distributed locking (`redis_lock`) using `cache.add` (Redis SET NX EX)
  with owner token verification.
- Atomic read-modify-write helpers for cached lists and counters.
"""

import logging
import secrets
import time
from contextlib import contextmanager
from typing import Any, Callable, List, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Release lock atomically via Lua script when underlying Redis client is available
_UNLOCK_LUA_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def safe_cache_get(key: str, default: Any = None) -> Any:
    """Safely fetch a value from Redis cache, returning default on error."""
    try:
        val = cache.get(key, default)
        return default if val is None else val
    except Exception as exc:
        logger.warning(f"Redis cache.get failed for key '{key}': {exc}")
        return default


def safe_cache_set(key: str, value: Any, timeout: Optional[int] = 300) -> bool:
    """Safely set a value in Redis cache, returning False on error."""
    try:
        cache.set(key, value, timeout=timeout)
        return True
    except Exception as exc:
        logger.warning(f"Redis cache.set failed for key '{key}': {exc}")
        return False


def safe_cache_add(key: str, value: Any, timeout: Optional[int] = 300) -> bool:
    """Atomically set a key only if it does not already exist (SET NX EX)."""
    try:
        return bool(cache.add(key, value, timeout=timeout))
    except Exception as exc:
        logger.warning(f"Redis cache.add failed for key '{key}': {exc}")
        return False


def safe_cache_delete(key: str) -> bool:
    """Safely delete a key from Redis cache."""
    try:
        cache.delete(key)
        return True
    except Exception as exc:
        logger.warning(f"Redis cache.delete failed for key '{key}': {exc}")
        return False


def _release_lock(lock_key: str, token: str) -> None:
    """Release a distributed lock only if still owned by `token`."""
    try:
        # Try atomic Lua release if raw redis client is accessible
        client_getter = getattr(cache, "_cache", None)
        if client_getter is not None and hasattr(client_getter, "get_client"):
            raw_client = client_getter.get_client(write=True)
            full_key = cache.make_key(lock_key)
            raw_client.eval(_UNLOCK_LUA_SCRIPT, 1, full_key, token)
            return
    except Exception:
        pass

    # Fallback to compare-and-delete via Django cache API
    try:
        if cache.get(lock_key) == token:
            cache.delete(lock_key)
    except Exception as exc:
        logger.warning(f"Failed to release lock '{lock_key}': {exc}")


@contextmanager
def redis_lock(
    lock_name: str,
    timeout: int = 30,
    wait_timeout: float = 10.0,
    poll_interval: float = 0.05,
):
    """
    Distributed lock backed by Redis (`cache.add`).

    Yields True if the lock was acquired, or False if acquisition timed out
    or Redis is unreachable (allowing callers to decide whether to proceed
    with a fallback or abort).
    """
    lock_key = f"lock:{lock_name}"
    token = secrets.token_hex(16)
    deadline = time.monotonic() + max(0.0, wait_timeout)
    acquired = False

    while True:
        try:
            if cache.add(lock_key, token, timeout=timeout):
                acquired = True
                break
        except Exception as exc:
            logger.warning(f"Redis lock error on '{lock_key}', proceeding unlocked: {exc}")
            break

        if time.monotonic() >= deadline:
            break
        time.sleep(poll_interval)

    try:
        yield acquired
    finally:
        if acquired:
            _release_lock(lock_key, token)


def update_cached_list(
    key: str,
    updater: Callable[[List[Any]], List[Any]],
    timeout: int = 86400,
    lock_timeout: int = 10,
) -> List[Any]:
    """
    Atomically read-modify-write a list stored in Redis under a distributed lock.
    """
    with redis_lock(f"list:{key}", timeout=lock_timeout, wait_timeout=5.0):
        current = safe_cache_get(key, [])
        if not isinstance(current, list):
            current = []
        updated = updater(list(current))
        safe_cache_set(key, updated, timeout=timeout)
        return updated


def append_to_cached_list(
    key: str,
    item: Any,
    timeout: int = 86400,
    max_items: int = 500,
) -> List[Any]:
    """
    Atomically append `item` to a cached list in Redis without race conditions.
    """
    def _append(items: List[Any]) -> List[Any]:
        items.append(item)
        if max_items and len(items) > max_items:
            items = items[-max_items:]
        return items

    return update_cached_list(key, _append, timeout=timeout)

