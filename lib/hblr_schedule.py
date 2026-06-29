# -*- coding: utf-8 -*-
"""Load NJT HBLR PDF timetable data precomputed into hblr_schedule_data.json."""

from __future__ import annotations

import datetime
import json
import os
import statistics

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

# App travel-direction keys → PDF timetable blocks in hblr_schedule_data.json.
TRAVEL_TO_PDF_DIRECTION = {
    "northbound": "north_to_hoboken",
    "to_liberty_state_park": "south_to_bayonne",
}

# Minutes from upstream station to branch terminal (from PDF column pairing).
SOUTH_BRANCH_OFFSETS = {
    "Newport": {"8th Street": 22, "West Side Ave": 21},
    "Exchange Place": {"8th Street": 16, "West Side Ave": 15},
    "Liberty State Park": {"8th Street": 13, "West Side Ave": 12},
    "8th Street": {"8th Street": 0},
    "West Side Ave": {"West Side Ave": 0},
}

SOUTH_BRANCH_DEST = {
    "8th Street": "8th St",
    "West Side Ave": "West Side Av",
}

_NORTH_BRANCHES = ("Hoboken", "Tonnelle Av")
_DEFAULT_BRANCH_HEADWAY = 20
WEEKEND_BRANCH_HEADWAY = 20
WEEKEND_WINDOW_NOON = 12 * 60
WEEKEND_WINDOW_END = 2 * 60  # 02:00
WEST_SIDE_TERMINAL_PHASE_LAG = 4  # vs 8th St; +1 min run-time diff => +5 at Newport/Exchange
BRANCH_TERMINAL_PHASE_LAG = {
    "8th Street": 0,
    "West Side Ave": WEST_SIDE_TERMINAL_PHASE_LAG,
}
# Continuous minutes from noon: 0 = 12:00, 720 = 00:00, 840 = 02:00.
WEEKEND_WINDOW_SPAN = (24 * 60 - WEEKEND_WINDOW_NOON) + WEEKEND_WINDOW_END


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


def _pdf_direction(travel_direction: str | None) -> str | None:
    if not travel_direction:
        return None
    return TRAVEL_TO_PDF_DIRECTION.get(travel_direction)


def departure_minutes(
    station_label: str,
    travel_direction: str | None = None,
    when: datetime.datetime | None = None,
) -> list[int]:
    """Return sorted departure minutes-from-midnight for a station/service day."""
    data = _load_data()
    if not data:
        return []
    when = when or datetime.datetime.now()
    day_key = service_day_key(when)

    pdf_dir = _pdf_direction(travel_direction)
    if pdf_dir and isinstance(data.get("directions"), dict):
        return list(
            data["directions"]
            .get(pdf_dir, {})
            .get(station_label, {})
            .get(day_key, [])
        )

    legacy = data.get("stations", {}).get(station_label, {}).get(day_key, [])
    if legacy and travel_direction == "to_liberty_state_park":
        return list(legacy)
    if legacy and travel_direction is None:
        return list(legacy)
    return []


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
    end = 0
    for start, stop, _headway in _schedule_windows(when):
        end = max(end, stop)
    return end if end else 24 * 60


def infer_headway_from_times(explicit: list[int], fallback: int = _DEFAULT_BRANCH_HEADWAY) -> int:
    """Median gap between PDF times on a single branch (typically 15–20 min)."""
    if len(explicit) < 2:
        return fallback
    gaps = [explicit[index + 1] - explicit[index] for index in range(len(explicit) - 1)]
    branch_gaps = [gap for gap in gaps if 10 <= gap <= 30]
    if branch_gaps:
        return int(statistics.median(branch_gaps))
    return fallback


def clock_to_weekend_offset(minute: int) -> int | None:
    """Map clock minute to continuous weekend window (12:00 → 02:00), or None if outside."""
    if WEEKEND_WINDOW_NOON <= minute < 24 * 60:
        return minute - WEEKEND_WINDOW_NOON
    if 0 <= minute <= WEEKEND_WINDOW_END:
        return (24 * 60 - WEEKEND_WINDOW_NOON) + minute
    return None


def weekend_offset_to_clock(offset: int) -> int:
    if offset < 24 * 60 - WEEKEND_WINDOW_NOON:
        return offset + WEEKEND_WINDOW_NOON
    return offset - (24 * 60 - WEEKEND_WINDOW_NOON)


def _weekend_branch_continuous_pool(
    explicit: list[int],
    headway: int = WEEKEND_BRANCH_HEADWAY,
    phase_lag: int = 0,
) -> list[int]:
    """Every `headway` min from 12:00 through 02:00 on a continuous timeline."""
    explicit_offsets = [
        offset
        for offset in (clock_to_weekend_offset(minute) for minute in explicit)
        if offset is not None
    ]
    phase = (min(explicit_offsets) % headway) if explicit_offsets else 0
    phase += phase_lag
    return list(range(phase, WEEKEND_WINDOW_SPAN + 1, headway))


def _eighth_terminal_weekend_pool(when: datetime.datetime) -> list[int]:
    explicit = departure_minutes("8th Street", "to_liberty_state_park", when)
    return _weekend_branch_continuous_pool(explicit, phase_lag=0)


def _terminal_weekend_continuous_pool(branch_station: str, when: datetime.datetime) -> list[int]:
    if branch_station == "8th Street":
        return _eighth_terminal_weekend_pool(when)
    if branch_station == "West Side Ave":
        return [
            offset + WEST_SIDE_TERMINAL_PHASE_LAG
            for offset in _eighth_terminal_weekend_pool(when)
        ]
    explicit = departure_minutes(branch_station, "to_liberty_state_park", when)
    phase_lag = BRANCH_TERMINAL_PHASE_LAG.get(branch_station, 0)
    return _weekend_branch_continuous_pool(explicit, phase_lag=phase_lag)


def _build_branch_pool(branch_station: str, when: datetime.datetime) -> list[int]:
    explicit = departure_minutes(branch_station, "to_liberty_state_park", when)
    if not explicit:
        return []
    if service_day_key(when) == "weekend":
        continuous = _terminal_weekend_continuous_pool(branch_station, when)
        return sorted(weekend_offset_to_clock(offset) for offset in continuous)
    headway = infer_headway_from_times(explicit)
    return extend_with_headway(explicit, headway, service_end_minute(when))


def branch_departures_in_weekend_window(
    station_label: str,
    when: datetime.datetime | None = None,
) -> dict[str, list[int]]:
    """Continuous-timeline departures per branch line in the 12:00–02:00 weekend window."""
    when = when or datetime.datetime.now()
    if when.weekday() < 5:
        return {}
    offsets = SOUTH_BRANCH_OFFSETS.get(station_label, {})
    eight_terminal = _eighth_terminal_weekend_pool(when)
    west_terminal = [offset + WEST_SIDE_TERMINAL_PHASE_LAG for offset in eight_terminal]
    branch_terminals = {
        "8th Street": eight_terminal,
        "West Side Ave": west_terminal,
    }
    result: dict[str, list[int]] = {}
    for branch_station, run_offset in offsets.items():
        terminal_continuous = branch_terminals.get(branch_station)
        if terminal_continuous is None:
            terminal_continuous = _terminal_weekend_continuous_pool(branch_station, when)
        destination = SOUTH_BRANCH_DEST[branch_station]
        upstream = sorted(
            {offset - run_offset for offset in terminal_continuous if offset >= run_offset}
        )
        result[destination] = upstream
    return result


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


def _train_dict(minutes: int, destination: str) -> dict:
    return {
        "line": None,
        "destination": destination,
        "minutes": minutes,
        "eta": "Due" if minutes == 0 else "~%dm" % minutes,
        "status": "SCHED",
        "estimated": True,
    }


def _south_branch_trains(
    station_label: str,
    now: datetime.datetime,
    count: int,
) -> list[dict]:
    """8th St and West Side Ave each keep their own ~20 min PDF branch schedule."""
    now_mod = now.hour * 60 + now.minute
    now_continuous = clock_to_weekend_offset(now_mod)
    offsets = SOUTH_BRANCH_OFFSETS.get(station_label, {})
    trains: list[dict] = []

    if service_day_key(now) == "weekend" and now_continuous is not None:
        eight_terminal = _eighth_terminal_weekend_pool(now)
        west_terminal = [offset + WEST_SIDE_TERMINAL_PHASE_LAG for offset in eight_terminal]
        branch_terminals = {
            "8th Street": eight_terminal,
            "West Side Ave": west_terminal,
        }
        for branch_station, run_offset in offsets.items():
            terminal_continuous = branch_terminals.get(branch_station)
            if terminal_continuous is None:
                terminal_continuous = _terminal_weekend_continuous_pool(branch_station, now)
            destination = SOUTH_BRANCH_DEST[branch_station]
            for offset in terminal_continuous:
                upstream = offset - run_offset
                if upstream < 0:
                    continue
                delta = upstream - now_continuous
                if delta < 0:
                    continue
                trains.append(_train_dict(delta, destination))
        trains.sort(key=lambda item: (item["minutes"], item["destination"]))
        return trains[: max(1, count)]

    for branch_station, offset in offsets.items():
        pool = _build_branch_pool(branch_station, now)
        if not pool:
            continue
        destination = SOUTH_BRANCH_DEST[branch_station]
        for minute in pool:
            delta = minute - offset - now_mod
            if delta < 0:
                continue
            trains.append(_train_dict(delta, destination))

    trains.sort(key=lambda item: (item["minutes"], item["destination"]))
    return trains[: max(1, count)]


def upcoming_departures(
    station: dict,
    travel_direction: str | None = None,
    now: datetime.datetime | None = None,
    count: int = 12,
) -> list[dict]:
    """Build offline train dicts from PDF timetable (+ branch headway fill)."""
    now = now or datetime.datetime.now()
    label = station["label"]

    if travel_direction == "to_liberty_state_park" and label in SOUTH_BRANCH_OFFSETS:
        return _south_branch_trains(label, now, count)

    headway = service_headway(now)
    if headway is None:
        return []

    explicit = departure_minutes(label, travel_direction, now)
    if explicit:
        fill_headway = infer_headway_from_times(explicit, fallback=headway)
        now_mod = now.hour * 60 + now.minute
        pool = extend_with_headway(explicit, fill_headway, service_end_minute(now))
        deltas = [minute - now_mod for minute in pool if minute >= now_mod]
    else:
        deltas = _headway_deltas(station, now, headway, count)

    branches = _NORTH_BRANCHES if travel_direction == "northbound" else _SOUTH_BRANCHES
    trains = []
    for index, delta in enumerate(deltas[: max(1, count)]):
        destination = branches[index % len(branches)]
        trains.append(_train_dict(delta, destination))
    return trains


# Legacy alias used in tests/docs.
_SOUTH_BRANCHES = ("8th St", "West Side Av")
