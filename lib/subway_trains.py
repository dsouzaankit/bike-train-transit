# -*- coding: utf-8 -*-
"""NYC subway departures — north/Queens and downtown toward JC."""

import re
import urllib.parse
from lib.parallel import map_parallel, run_parallel

SUBWAY_API_BASE = "https://subwayinfo.nyc/api/arrivals"
SUBWAY_DIRECTION_NORTH = "N"
SUBWAY_DIRECTION_SOUTH = "S"
SUBWAY_MAX_TRAINS = 2
SUBWAY_FETCH_LIMIT = 10
CANAL_WTC_ESTIMATE_MINUTES = 2
PATH_SUBWAY_WALK_MINUTES = {
    "Christopher St": 5,
    "West 4 St": 7,
}

# West 4 St-Wash Sq uses separate stop IDs for ACE vs BDFM platforms.
SUBWAY_STATIONS_NORTH = [
    {"station_id": "133", "label": "Christopher St", "direction": SUBWAY_DIRECTION_NORTH},
    {"station_id": ["A32", "D20"], "label": "West 4 St", "direction": SUBWAY_DIRECTION_NORTH},
]

SUBWAY_WTC_CORTLANDT = {
    "station_id": "138",
    "label": "WTC Cortlandt",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_WTC_E = {
    "station_id": "E01",
    "label": "World Trade Center",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_CANAL_ACE = {
    "station_id": "A34",
    "label": "Canal St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

_HEADSIGN_SHORT = {
    "Van Cortlandt Park-242 St": "Van Cortlandt",
    "Inwood-207 St": "Inwood",
    "168 St": "168 St",
    "Jamaica Center": "Jamaica",
    "Jamaica-179 St": "Jamaica",
    "Norwood-205 St": "Norwood",
    "South Ferry": "South Ferry",
    "World Trade Center": "WTC",
}


def _short_headsign(name):
    if not name:
        return "?"
    text = str(name).strip()
    if text in _HEADSIGN_SHORT:
        return _HEADSIGN_SHORT[text]
    if "-242 St" in text:
        return text.split("-", 1)[0]
    if len(text) > 18:
        return text[:16] + "..."
    return text


def _coerce_minutes(value):
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _format_eta(minutes, estimated=False):
    if minutes is None:
        return "?"
    prefix = "~" if estimated else ""
    if minutes <= 0:
        return "Due"
    return prefix + "%sm" % minutes


def _normalize_arrival(item, extra_minutes=0, estimated=False):
    if not isinstance(item, dict):
        return None
    minutes = _coerce_minutes(item.get("minutesAway"))
    if minutes is not None and extra_minutes:
        minutes = minutes + extra_minutes
    line = item.get("line")
    return {
        "line": str(line) if line not in (None, "") else "?",
        "destination": _short_headsign(item.get("headsign")),
        "minutes": minutes,
        "eta": _format_eta(minutes, estimated=estimated),
        "status": "ON_TIME",
        "estimated": estimated,
    }


def _sort_arrivals(arrivals):
    out = []
    for item in arrivals or []:
        norm = _normalize_arrival(item)
        if norm is not None:
            out.append(norm)
    out.sort(
        key=lambda t: (
            t.get("minutes") if t.get("minutes") is not None else 9999,
        )
    )
    return out


def _fetch_arrivals(station_id, fetch_json, direction, limit=6):
    query = urllib.parse.urlencode(
        {
            "station_id": station_id,
            "direction": direction,
            "limit": str(limit),
        }
    )
    payload = fetch_json(SUBWAY_API_BASE + "?" + query)
    if not isinstance(payload, dict):
        raise ValueError("Unexpected subway API response for %s" % station_id)
    return payload


def _is_wtc_bound_headsign(headsign):
    text = (headsign or "").casefold()
    return "world trade" in text or text.strip() == "wtc"


def _is_south_ferry_headsign(headsign):
    text = (headsign or "").casefold()
    return "south ferry" in text


def fetch_station_arrivals(station, fetch_json, limit=6, headsign_filter=None):
    station_ids = station["station_id"]
    direction = station.get("direction", SUBWAY_DIRECTION_NORTH)
    if isinstance(station_ids, str):
        station_ids = [station_ids]
    arrivals = []

    def _load_one(station_id):
        payload = _fetch_arrivals(station_id, fetch_json, direction, limit=limit)
        return payload.get("arrivals") or []

    if len(station_ids) == 1:
        arrivals.extend(_load_one(station_ids[0]))
    else:
        for chunk in map_parallel(station_ids, _load_one):
            if chunk:
                arrivals.extend(chunk)

    if headsign_filter is not None:
        arrivals = [a for a in arrivals if headsign_filter(a.get("headsign"))]
    return _sort_arrivals(arrivals)


def _load_simple_board(
    station,
    fetch_json,
    max_trains,
    headsign_filter=None,
    fetch_limit=8,
):
    error = None
    trains = []
    try:
        trains = fetch_station_arrivals(
            station,
            fetch_json,
            limit=fetch_limit,
            headsign_filter=headsign_filter,
        )
    except Exception as exc:
        error = str(exc)
    return {
        "label": station["label"],
        "trains": trains[:max_trains],
        "error": error if not trains else None,
    }


def _load_world_trade_center_board(fetch_json, max_trains=SUBWAY_MAX_TRAINS):
    error = None
    try:
        trains = fetch_station_arrivals(SUBWAY_WTC_E, fetch_json)
        if trains:
            return {
                "label": "World Trade Center",
                "trains": trains[:max_trains],
                "error": None,
                "estimated": False,
            }
    except Exception as exc:
        error = str(exc)

    try:
        raw = []
        payload = _fetch_arrivals(
            SUBWAY_CANAL_ACE["station_id"],
            fetch_json,
            SUBWAY_CANAL_ACE["direction"],
            limit=8,
        )
        for item in payload.get("arrivals") or []:
            if not _is_wtc_bound_headsign(item.get("headsign")):
                continue
            norm = _normalize_arrival(
                item,
                extra_minutes=CANAL_WTC_ESTIMATE_MINUTES,
                estimated=True,
            )
            if norm is not None:
                raw.append(norm)
        raw.sort(key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999)
        if raw:
            return {
                "label": "World Trade Center",
                "trains": raw[:max_trains],
                "error": None,
                "estimated": True,
                "note": "est. Canal St + %s min" % CANAL_WTC_ESTIMATE_MINUTES,
            }
    except Exception as exc:
        if error is None:
            error = str(exc)

    return {
        "label": "World Trade Center",
        "trains": [],
        "error": error or "No WTC-bound trains",
        "estimated": False,
    }


def _earliest_path_arrival_minutes(path_boards):
    earliest = None
    for board in path_boards or []:
        for train in board.get("trains") or []:
            minutes = train.get("minutes")
            if minutes is None:
                continue
            if earliest is None or minutes < earliest:
                earliest = minutes
    return earliest


def apply_path_subway_connections(
    subway_boards,
    path_33rd_boards,
    max_trains=SUBWAY_MAX_TRAINS,
):
    """Keep subway departures reachable after earliest PATH at Christopher / 9th St."""
    earliest_path = _earliest_path_arrival_minutes(path_33rd_boards)
    if earliest_path is None:
        return subway_boards

    connected = []
    for board in subway_boards or []:
        walk = PATH_SUBWAY_WALK_MINUTES.get(board.get("label"), 5)
        threshold = earliest_path + walk
        catchable = []
        for train in board.get("trains") or []:
            minutes = train.get("minutes")
            if minutes is not None and minutes >= threshold:
                catchable.append(train)

        note = "after PATH +%s min" % walk
        if board.get("note"):
            note = board["note"] + " · " + note

        new_board = dict(board)
        new_board["note"] = note
        new_board["trains"] = catchable[:max_trains]
        if catchable:
            new_board["error"] = None
        connected.append(new_board)
    return connected


def get_subway_north_boards(fetch_json, max_trains=SUBWAY_MAX_TRAINS):
    boards = []

    def _load_board(station):
        return _load_simple_board(
            station,
            fetch_json,
            max_trains=SUBWAY_FETCH_LIMIT,
            fetch_limit=SUBWAY_FETCH_LIMIT,
        )

    for board in map_parallel(SUBWAY_STATIONS_NORTH, _load_board):
        if board is not None:
            boards.append(board)
    boards.sort(key=lambda b: b["label"])
    return boards


def get_subway_to_jc_boards(fetch_json, max_trains=SUBWAY_MAX_TRAINS):
    boards = []

    def _cortlandt():
        return _load_simple_board(
            SUBWAY_WTC_CORTLANDT,
            fetch_json,
            max_trains,
            headsign_filter=_is_south_ferry_headsign,
        )

    results = run_parallel(
        {
            "cortlandt": _cortlandt,
            "wtc": lambda: _load_world_trade_center_board(fetch_json, max_trains),
        }
    )
    if results.get("cortlandt") is not None:
        boards.append(results["cortlandt"])
    if results.get("wtc") is not None:
        boards.append(results["wtc"])
    return boards


def print_subway_boards(boards, title="Subway"):
    print(title)
    for board in boards:
        print("")
        label = board["label"]
        if board.get("estimated"):
            label += " (est.)"
        print(label)
        if board.get("note"):
            print("  %s" % board["note"])
        if board.get("error"):
            print("  unavailable (%s)" % board["error"])
            continue
        trains = board.get("trains") or []
        if not trains:
            print("  no upcoming trains")
            continue
        for train in trains:
            print("  %s  %s -> %s" % (train["eta"], train["line"], train["destination"]))
