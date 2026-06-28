# -*- coding: utf-8 -*-
"""Load NJT HBLR PDF timetable data precomputed into hblr_schedule_data.json."""

from __future__ import annotations

import datetime
import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hblr_schedule_data.json")
_CACHE: dict | None = None

_SCHED_WEEKDAY = (
    (5 * 60, 6 * 60 + 30, 12),
    (6 * 60 + 30, 9 * 60 + 30, 6),
    (9 * 60 + 30, 15 * 60 + 30, 10),
    (15 * 60 + 30, 19 * 60, 6),
    (19 * 60, 22 * 60, 10),
    (22 * 60, 24 * 60, 15),
    (0, 60, 20),
)
_SCHED_SATURDAY = ((0, 90, 20), (5 * 60 + 30, 24 * 60, 12))
_SCHED_SUNDAY = ((0, 90, 20), (6 * 60, 24 * 60, 15))
_SOUTH_BRANCHES = ("8th St", "West Side Av")


def _load_data() -> dict | None:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as fh:
            _CACHE = json.load(fh)
    except (OSError, ValueError):
        _CACHE = None
    return _CACHE


def service_day_key(when: datetime.datetime | None = None) -> str:
    when = when or datetime.datetime.now()
    return "weekend" if when.weekday() >= 5 else "weekday"


def departure_minutes(station_label: str, when: datetime.datetime | None = None) -> list[int]:
    """Return sorted departure minutes-from-midnight for a station/service day."""
    data = _load_data()
    if not data:
        return []
    when = when or datetime.datetime.now()
    day_key = service_day_key(when)
    return list(data.get("stations", {}).get(station_label, {}).get(day_key, []))


def _schedule_windows(when: datetime.datetime):
    weekday = when.weekday()
    if weekday <= 4:
        return _SCHED_WEEKDAY
    if weekday == 5:
        return _SCHED_SATURDAY
    return _SCHED_SUNDAY


def service_headway(now: datetime.datetime) -> int | None:
    minute_of_day = now.hour * 60 + now.minute
    for start, end, headway in _schedule_windows(now):
        if start <= minute_of_day < end:
            return headway
    return None


def service_end_minute(when: datetime.datetime) -> int:
    """Last minute of HBLR service for the day (from offline headway windows)."""
    end = 0
    for start, stop, _headway in _schedule_windows(when):
        end = max(end, stop)
    return end if end else 24 * 60


def extend_with_headway(
    departures: list[int],
    headway: int,
    service_end: int,
) -> list[int]:
    """Append headway-spaced departures after the last explicit PDF time."""
    if headway <= 0 or not departures:
        return list(departures)
    merged = set(departures)
    cursor = departures[-1] + headway
    while cursor <= service_end:
        merged.add(cursor)
        cursor += headway
    return sorted(merged)


def _headway_deltas(station: dict, now: datetime.datetime, headway: int, count: int) -> list[int]:
    phase = station.get("phase", 0) % headway
    first = (phase - now.minute) % headway
    if first == 0 and (now.hour * 60 + now.minute) > 0:
        first = headway
    return [first + index * headway for index in range(max(1, count * 2))]


def upcoming_departures(
    station: dict,
    now: datetime.datetime | None = None,
    count: int = 12,
) -> list[dict]:
    """Build offline train dicts from PDF timetable (+ headway fill after last listed time)."""
    now = now or datetime.datetime.now()
    headway = service_headway(now)
    if headway is None:
        return []

    label = station["label"]
    explicit = departure_minutes(label, now)
    if explicit:
        now_mod = now.hour * 60 + now.minute
        pool = extend_with_headway(explicit, headway, service_end_minute(now))
        deltas = [minute - now_mod for minute in pool if minute >= now_mod]
    else:
        deltas = _headway_deltas(station, now, headway, count)

    trains = []
    for index, delta in enumerate(deltas[: max(1, count)]):
        branch = _SOUTH_BRANCHES[index % len(_SOUTH_BRANCHES)]
        trains.append(
            {
                "line": None,
                "destination": branch,
                "minutes": delta,
                "eta": "Due" if delta == 0 else "~%dm" % delta,
                "status": "SCHED",
                "estimated": True,
            }
        )
    return trains
