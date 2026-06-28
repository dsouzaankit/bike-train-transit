# -*- coding: utf-8 -*-
"""Global simulated clock — a single app-wide whole-hour offset.

Setting a non-zero offset lets you preview the app's *time-derived* state as if
it were a different moment. It shifts every reading of "now" that flows through
this module: the PATH / HBLR offline schedules, displayed timestamps, and any
timestamp-based ETA math.

The offset is a whole number of hours, clamped to ``[-23, 23]``.

Caveat: live API feeds return real-time data, so under a simulated clock the
PATH and HBLR boards fall back to their offline schedule estimates (see
``path_schedule.py`` / ``light_rail.py``); subway and tunnel feeds have no
offline model and keep showing real-time data.

Configure it via (in order of precedence):
  1. ``set_offset_hours(...)`` at runtime (e.g. the in-app Sim button or
     the ``--sim-hours`` CLI flag),
  2. the persisted value written by ``save_offset()`` (``sim_offset.json``),
  3. the ``BTT_SIM_HOUR_OFFSET`` environment variable,
  4. the ``SIM_HOUR_OFFSET`` constant in ``bike_train_transit.py`` (default).
"""

import datetime as _dt
import json
import os

ENV_VAR = "BTT_SIM_HOUR_OFFSET"

# Whole-hour offsets only; clamped to +/- a full day minus one hour.
OFFSET_MIN = -23
OFFSET_MAX = 23

# Persisted across launches so an in-app change survives the Shortcut relaunch.
_STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim_offset.json"
)

_OFFSET_HOURS = 0


def _clamp_int(hours):
    try:
        value = int(round(float(hours or 0)))
    except (TypeError, ValueError):
        value = 0
    return max(OFFSET_MIN, min(OFFSET_MAX, value))


def set_offset_hours(hours):
    """Set the global offset as a whole-hour int, clamped to [-23, 23]."""
    global _OFFSET_HOURS
    _OFFSET_HOURS = _clamp_int(hours)
    return _OFFSET_HOURS


def get_offset_hours():
    return _OFFSET_HOURS


def _read_persisted():
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and data.get("offset_hours") is not None:
        return data.get("offset_hours")
    return None


def save_offset():
    """Persist the current offset so it survives a relaunch. Returns bool."""
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"offset_hours": _OFFSET_HOURS}, fh)
        return True
    except OSError:
        return False


def load_offset(default=0):
    """Initialize the offset: persisted value, else env var, else ``default``."""
    persisted = _read_persisted()
    if persisted is not None:
        return set_offset_hours(persisted)
    raw = os.environ.get(ENV_VAR)
    if raw is not None and str(raw).strip() != "":
        return set_offset_hours(raw)
    return set_offset_hours(default)


def _delta():
    return _dt.timedelta(hours=_OFFSET_HOURS)


def now():
    """Local wall-clock time shifted by the global offset."""
    return _dt.datetime.now() + _delta()


def utcnow():
    """UTC time shifted by the global offset."""
    return _dt.datetime.utcnow() + _delta()


def is_simulated():
    return _OFFSET_HOURS != 0


def offset_label():
    """Compact label like ``+3h`` / ``-2h``; empty when not simulated."""
    if not is_simulated():
        return ""
    return "%+dh" % _OFFSET_HOURS
