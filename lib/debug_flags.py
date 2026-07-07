# -*- coding: utf-8 -*-
"""Debug toggles — disable data sources via BIKE_TRAIN_TRANSIT_INACTIVE or --inactive."""

from __future__ import annotations

import os

_ENV_KEY = "BIKE_TRAIN_TRANSIT_INACTIVE"
_SOURCES = frozenset({"citibike", "path", "subway", "hblr"})


def inactive_sources() -> frozenset[str]:
    raw = os.environ.get(_ENV_KEY, "")
    parts = {part.strip().lower() for part in raw.split(",") if part.strip()}
    unknown = parts - _SOURCES
    if unknown:
        raise ValueError(
            "Unknown %s value(s): %s (expected: %s)"
            % (_ENV_KEY, ", ".join(sorted(unknown)), ", ".join(sorted(_SOURCES)))
        )
    return frozenset(parts)


def is_active(source: str) -> bool:
    return source.lower() not in inactive_sources()


def inactive_summary() -> str:
    items = sorted(inactive_sources())
    return ", ".join(items)


def set_inactive(*sources: str) -> None:
    """Replace inactive set (bike_train_transit.py --inactive or env)."""
    normalized = []
    for source in sources:
        key = source.strip().lower()
        if key not in _SOURCES:
            raise ValueError("Unknown debug source %r" % source)
        normalized.append(key)
    os.environ[_ENV_KEY] = ",".join(sorted(set(normalized)))
