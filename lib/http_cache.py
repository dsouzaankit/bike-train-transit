# -*- coding: utf-8 -*-
"""Persistent HTTP JSON cache — reuse responses for 2 minutes across app restarts."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.parse

HTTP_CACHE_TTL_SEC = 120
_CACHE_DIR_NAME = "http_cache"
_memory: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()
_cache_dir_override: str | None = None
_stats = {"hits": 0, "misses": 0, "stores": 0, "disk_errors": 0}


def stats_snapshot() -> dict[str, int]:
    with _lock:
        return dict(_stats)


def reset_stats() -> None:
    with _lock:
        for key in _stats:
            _stats[key] = 0


def _record_hit() -> None:
    with _lock:
        _stats["hits"] += 1


def _record_miss() -> None:
    with _lock:
        _stats["misses"] += 1


def _record_store() -> None:
    with _lock:
        _stats["stores"] += 1


def _record_disk_error() -> None:
    with _lock:
        _stats["disk_errors"] += 1


def disk_entry_count() -> int:
    try:
        return sum(
            1 for name in os.listdir(_cache_dir()) if name.endswith(".json")
        )
    except OSError:
        return 0


def _cache_dir() -> str:
    if _cache_dir_override is not None:
        return _cache_dir_override
    from .log_paths import app_root

    path = os.path.join(app_root(), _CACHE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def set_cache_dir_for_tests(path: str | None) -> None:
    """Point cache at a temp directory (tests only)."""
    global _cache_dir_override
    _cache_dir_override = path
    clear_memory()


def normalize_cache_url(url: str) -> str:
    """Stable cache key — drop PANYNJ cache-bust ``_`` query param only."""
    parsed = urllib.parse.urlparse(url)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [(key, value) for key, value in pairs if key != "_"]
    filtered.sort()
    query = urllib.parse.urlencode(filtered)
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, "")
    )


def _entry_key(url: str) -> str:
    return hashlib.sha256(normalize_cache_url(url).encode("utf-8")).hexdigest()


def _entry_path(key: str) -> str:
    return os.path.join(_cache_dir(), key + ".json")


def clear_memory() -> None:
    with _lock:
        _memory.clear()


def clear_disk() -> None:
    directory = _cache_dir()
    try:
        for name in os.listdir(directory):
            if name.endswith(".json"):
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass
    except OSError:
        pass


def clear_all() -> None:
    clear_memory()
    clear_disk()
    reset_stats()


def _read_disk(key: str, now: float) -> object | None:
    path = _entry_path(key)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            envelope = json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(envelope, dict):
        return None
    stored_at = envelope.get("stored_at")
    payload = envelope.get("payload")
    if stored_at is None or now - float(stored_at) > HTTP_CACHE_TTL_SEC:
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    return payload


def _write_disk(key: str, url: str, payload: object, now: float) -> None:
    path = _entry_path(key)
    tmp = path + ".tmp"
    envelope = {
        "stored_at": now,
        "url": normalize_cache_url(url),
        "payload": payload,
    }
    try:
        data = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except (OSError, TypeError, ValueError):
        _record_disk_error()
        try:
            os.remove(tmp)
        except OSError:
            pass


def get_cached_json(url: str) -> object | None:
    if os.environ.get("BIKE_TRAIN_TRANSIT_NO_HTTP_CACHE"):
        return None
    key = _entry_key(url)
    now = time.time()
    with _lock:
        cached = _memory.get(key)
        if cached and now - cached[0] <= HTTP_CACHE_TTL_SEC:
            _stats["hits"] += 1
            return cached[1]
    payload = _read_disk(key, now)
    if payload is None:
        return None
    with _lock:
        _memory[key] = (now, payload)
        _stats["hits"] += 1
    return payload


def store_cached_json(url: str, payload: object) -> None:
    if os.environ.get("BIKE_TRAIN_TRANSIT_NO_HTTP_CACHE"):
        return
    key = _entry_key(url)
    now = time.time()
    with _lock:
        _memory[key] = (now, payload)
        _stats["stores"] += 1
    try:
        _write_disk(key, url, payload, now)
    except (OSError, TypeError, ValueError):
        pass
