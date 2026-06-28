# -*- coding: utf-8 -*-
"""Offline PATH schedule estimate — used when the simulated clock is active.

Live PANYNJ data always reflects *real* now, so once you shift the global clock
(``lib.clock``) to another time the live ETAs no longer make sense. When a
simulation offset is set, the PATH boards fall back to this clock-face headway
model instead, mirroring the HBLR offline schedule.

This is an approximation of PATH service patterns (peak / off-peak / weekend /
overnight, including the overnight JSQ<->33rd "via Hoboken" routing). Every
train it produces is flagged ``estimated`` and noted ``sched`` in the UI.
"""

from . import clock

# Route keys used below:
#   NWK_WTC  Newark <-> World Trade Center
#   HOB_WTC  Hoboken <-> World Trade Center
#   JSQ_33   Journal Square <-> 33rd St
#   HOB_33   Hoboken <-> 33rd St
#   JSQ_33H  Journal Square <-> 33rd St *via Hoboken* (overnight pattern)
#
# Headway (minutes) per route per service mode; None = route not running then.
_HEADWAYS = {
    "NWK_WTC": {"peak": 8, "off": 12, "night": 20, "wknd": 15, "wknd_night": 20},
    "HOB_WTC": {"peak": 10, "off": 15, "night": None, "wknd": 18, "wknd_night": None},
    "JSQ_33": {"peak": 6, "off": 12, "night": None, "wknd": 14, "wknd_night": None},
    "HOB_33": {"peak": 10, "off": 16, "night": None, "wknd": 18, "wknd_night": None},
    "JSQ_33H": {"peak": None, "off": None, "night": 20, "wknd": None, "wknd_night": 20},
}

# Per-direction station -> list of (route_key, destination_label, phase_min).
# `phase` staggers the clock-face so sibling stations differ realistically.
_NYC = {
    "Grove St PATH": [("NWK_WTC", "WTC", 0), ("JSQ_33", "33rd St", 2), ("JSQ_33H", "33rd St", 2)],
    "Newport PATH": [
        ("HOB_WTC", "WTC", 0),
        ("JSQ_33", "33rd St", 3),
        ("HOB_33", "33rd St", 6),
        ("JSQ_33H", "33rd St", 3),
    ],
    "Christopher St": [("JSQ_33", "33rd St", 1), ("HOB_33", "33rd St", 5), ("JSQ_33H", "33rd St", 1)],
    "9th St": [("JSQ_33", "33rd St", 2), ("HOB_33", "33rd St", 6), ("JSQ_33H", "33rd St", 2)],
    "14 St PATH": [("JSQ_33", "33rd St", 3), ("HOB_33", "33rd St", 7), ("JSQ_33H", "33rd St", 3)],
}
_NJ = {
    "Christopher St": [
        ("JSQ_33", "JSQ", 4),
        ("HOB_33", "Hoboken", 8),
        ("JSQ_33H", "JSQ via Hob", 4),
    ],
    "9th St": [("JSQ_33", "JSQ", 5), ("HOB_33", "Hoboken", 9), ("JSQ_33H", "JSQ via Hob", 5)],
    "33rd St": [("JSQ_33", "JSQ", 0), ("HOB_33", "Hoboken", 5), ("JSQ_33H", "JSQ via Hob", 0)],
    "World Trade Center": [("NWK_WTC", "Newark", 0), ("HOB_WTC", "Hoboken", 4)],
}

_DIR_MAPS = {"nyc": _NYC, "nj": _NJ}


def _mode(now):
    """Classify `now` into a service mode key used by ``_HEADWAYS``."""
    minute = now.hour * 60 + now.minute
    night = minute < 5 * 60 or minute >= 23 * 60
    if now.weekday() >= 5:
        return "wknd_night" if night else "wknd"
    if night:
        return "night"
    peak = (7 * 60 <= minute < 9 * 60 + 30) or (16 * 60 <= minute < 19 * 60)
    return "peak" if peak else "off"


def _route_headway(route_key, mode):
    return _HEADWAYS.get(route_key, {}).get(mode)


def _route_trains(route_key, dest, phase, now, mode, count=4):
    """Clock-face departures for one route at one station, or [] if not running."""
    headway = _route_headway(route_key, mode)
    if not headway:
        return []
    phase = phase % headway
    first = (phase - now.minute) % headway
    trains = []
    for i in range(max(1, count)):
        minutes = first + i * headway
        trains.append(
            {
                "destination": dest,
                "minutes": minutes,
                "eta": "Due" if minutes == 0 else "~%dm" % minutes,
                "status": "SCHED",
                "estimated": True,
            }
        )
    return trains


def offline_board(label, direction, now=None, max_trains=2):
    """Return a scheduled board dict for one station, or None if unmapped."""
    routes = _DIR_MAPS.get(direction, {}).get(label)
    if routes is None:
        return None
    now = now or clock.now()
    mode = _mode(now)
    trains = []
    for route_key, dest, phase in routes:
        trains.extend(_route_trains(route_key, dest, phase, now, mode))
    trains.sort(key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999)
    running = bool(trains)
    return {
        "label": label,
        "trains": trains[:max_trains],
        "error": None,
        "estimated": True,
        "note": "sched" if running else "no service now",
    }


def offline_boards(labels, direction, now=None, max_trains=2):
    now = now or clock.now()
    boards = []
    for label in labels:
        board = offline_board(label, direction, now=now, max_trains=max_trains)
        if board is None:
            board = {"label": label, "trains": [], "error": None, "estimated": True, "note": "sched n/a"}
        boards.append(board)
    return boards
