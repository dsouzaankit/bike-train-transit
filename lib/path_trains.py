# -*- coding: utf-8 -*-
"""PATH train departures — NYC-bound, 33rd-bound, and NJ-bound."""

import re
import time
from datetime import datetime

PATH_API_BASE = "https://path.api.razza.dev/v1/stations"
PANYNJ_PATH_URL = "https://www.panynj.gov/bin/portauthority/ridepath.json"
PATH_DIRECTION_NYC = "TO_NY"
PATH_DIRECTION_NJ = "TO_NJ"
PATH_MAX_TRAINS = 2
PATH_33RD_MAX_TRAINS = 1

# slug = path.api.razza.dev name; panynj = ridepath.json consideredStation code
PATH_STATIONS = [
    {"slug": "grove_street", "panynj": "GRV", "label": "Grove St PATH"},
    {"slug": "newport", "panynj": "NEW", "label": "Newport PATH"},
]

PATH_33RD_STATIONS = [
    {"slug": "christopher_street", "panynj": "CHR", "label": "Christopher St"},
    {"slug": "ninth_street", "panynj": "09S", "label": "9th St"},
]

PATH_NJ_STATIONS = [
    {"slug": "christopher_street", "panynj": "CHR", "label": "Christopher St"},
    {"slug": "ninth_street", "panynj": "09S", "label": "9th St"},
    {"slug": "thirty_third_street", "panynj": "33S", "label": "33rd St"},
    {"slug": "world_trade_center", "panynj": "WTC", "label": "World Trade Center"},
]

_DEST_SHORT = {
    "World Trade Center": "WTC",
    "33rd Street": "33rd St",
    "Journal Square": "JSQ",
    "Hoboken": "Hoboken",
    "Newark": "Newark",
}


def _short_destination(name):
    if not name:
        return "?"
    text = name.strip()
    for full, short in _DEST_SHORT.items():
        if text == full:
            return short
        if text.startswith(full + " "):
            return short + text[len(full) :]
    return text


def _is_33rd_destination(name):
    text = (name or "").casefold()
    if "world trade" in text or text.strip() == "wtc":
        return False
    return bool(re.search(r"33(?:rd|\s*st)", text))


def _parse_utc_iso(iso_text):
    if not iso_text:
        return None
    text = iso_text.strip().replace("Z", "")
    if "." in text:
        text = text.split(".", 1)[0]
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _minutes_until_utc(iso_text):
    when = _parse_utc_iso(iso_text)
    if when is None:
        return None
    delta = (when - datetime.utcnow()).total_seconds() / 60.0
    return max(0, int(round(delta)))


def _parse_eta_message(text):
    if not text:
        return None, "?"
    raw = text.strip()
    lower = raw.lower()
    if lower in ("due", "arriving", "arriving now"):
        return 0, raw
    if "delay" in lower:
        return 0, raw
    match = re.search(r"(\d+)", raw)
    if match:
        return int(match.group(1)), raw
    return None, raw


def _format_eta(minutes, eta_text):
    if eta_text and "delay" in eta_text.lower():
        return eta_text
    if minutes is None:
        return eta_text or "?"
    if minutes <= 0:
        return "Due"
    if minutes == 1:
        return "1 min"
    return "%s min" % minutes


def _normalize_train(destination, minutes, eta_text, status):
    return {
        "destination": _short_destination(destination),
        "minutes": minutes,
        "eta": _format_eta(minutes, eta_text),
        "status": status or "ON_TIME",
    }


def _filter_sort_trains(trains):
    out = [t for t in trains if t.get("minutes") is not None or t.get("eta")]
    out.sort(
        key=lambda t: (
            0 if t.get("status") == "ARRIVING_NOW" else 1,
            t.get("minutes") if t.get("minutes") is not None else 9999,
        )
    )
    return out


def _is_nyc_direction(label):
    text = (label or "").upper().replace(" ", "")
    return text == "TONY"


def _is_nj_direction(label):
    text = (label or "").upper().replace(" ", "")
    return text == "TONJ"


def _panynj_url():
    return PANYNJ_PATH_URL + "?_=" + str(int(time.time() * 1000))


def _fetch_panynj_payload(fetch_json):
    return fetch_json(_panynj_url())


def _fetch_razza_station(slug, fetch_json, direction=PATH_DIRECTION_NYC, dest_filter=None):
    payload = fetch_json(PATH_API_BASE + "/" + slug + "/realtime")
    trains = []
    for item in payload.get("upcomingTrains") or []:
        item_direction = (item.get("direction") or "").upper()
        if direction and item_direction and item_direction != direction:
            continue
        dest = item.get("headsign") or item.get("lineName") or "?"
        if dest_filter is not None and not dest_filter(dest):
            continue
        minutes = _minutes_until_utc(item.get("projectedArrival"))
        trains.append(
            _normalize_train(
                dest,
                minutes,
                None,
                item.get("status"),
            )
        )
    return _filter_sort_trains(trains)


def _parse_panynj_station(code, payload, direction_filter, dest_filter=None):
    for result in payload.get("results") or []:
        if result.get("consideredStation") != code:
            continue
        trains = []
        for dest in result.get("destinations") or []:
            if not direction_filter(dest.get("label")):
                continue
            for msg in dest.get("messages") or []:
                headsign = msg.get("headSign") or "?"
                if dest_filter is not None and not dest_filter(headsign):
                    continue
                minutes, eta_text = _parse_eta_message(msg.get("arrivalTimeMessage"))
                trains.append(
                    _normalize_train(
                        headsign,
                        minutes,
                        eta_text,
                        msg.get("status"),
                    )
                )
        return _filter_sort_trains(trains)
    return []


def _board_from_payload(
    station,
    payload,
    direction_filter,
    dest_filter=None,
    max_trains=PATH_MAX_TRAINS,
):
    trains = _parse_panynj_station(
        station["panynj"],
        payload,
        direction_filter,
        dest_filter=dest_filter,
    )
    return {
        "label": station["label"],
        "trains": trains[:max_trains],
        "error": None,
    }


def _maybe_enrich_with_razza(board, station, fetch_json, direction, dest_filter=None, max_trains=PATH_MAX_TRAINS):
    if board.get("trains"):
        return board
    try:
        trains = _fetch_razza_station(
            station["slug"],
            fetch_json,
            direction=direction,
            dest_filter=dest_filter,
        )
    except Exception as exc:
        board = dict(board)
        board["error"] = str(exc)
        return board
    if trains:
        board = dict(board)
        board["trains"] = trains[:max_trains]
        board["error"] = None
    return board


def _load_boards_from_payload(
    stations,
    payload,
    fetch_json,
    direction=PATH_DIRECTION_NYC,
    direction_filter=_is_nyc_direction,
    dest_filter=None,
    max_trains=PATH_MAX_TRAINS,
    try_razza=False,
):
    boards = []
    for station in stations:
        board = _board_from_payload(
            station,
            payload,
            direction_filter,
            dest_filter=dest_filter,
            max_trains=max_trains,
        )
        if try_razza and not board.get("trains"):
            board = _maybe_enrich_with_razza(
                board,
                station,
                fetch_json,
                direction,
                dest_filter=dest_filter,
                max_trains=max_trains,
            )
        boards.append(board)
    return boards


def _load_boards(
    stations,
    fetch_json,
    direction=PATH_DIRECTION_NYC,
    direction_filter=_is_nyc_direction,
    dest_filter=None,
    max_trains=PATH_MAX_TRAINS,
    panynj_payload=None,
):
    error = None
    payload = panynj_payload
    try:
        if payload is None:
            payload = _fetch_panynj_payload(fetch_json)
    except Exception as exc:
        error = str(exc)
        payload = None

    if payload is not None:
        boards = _load_boards_from_payload(
            stations,
            payload,
            fetch_json,
            direction=direction,
            direction_filter=direction_filter,
            dest_filter=dest_filter,
            max_trains=max_trains,
        )
        if any(board.get("trains") for board in boards):
            return boards, payload

    boards = []
    for station in stations:
        board = {
            "label": station["label"],
            "trains": [],
            "error": error,
        }
        board = _maybe_enrich_with_razza(
            board,
            station,
            fetch_json,
            direction,
            dest_filter=dest_filter,
            max_trains=max_trains,
        )
        boards.append(board)
    return boards, payload


def get_all_path_boards(
    fetch_json,
    razza_fetch_json=None,
    max_trains=PATH_MAX_TRAINS,
    max_33rd_trains=PATH_33RD_MAX_TRAINS,
):
    """Fetch PANYNJ once and build NYC, 33rd, and NJ boards."""
    razza_fetch = razza_fetch_json or fetch_json
    payload = None
    fetch_error = None
    try:
        payload = _fetch_panynj_payload(fetch_json)
    except Exception as exc:
        fetch_error = str(exc)

    def _build(stations, direction, direction_filter, dest_filter, limit):
        if payload is not None:
            return _load_boards_from_payload(
                stations,
                payload,
                fetch_json,
                direction=direction,
                direction_filter=direction_filter,
                dest_filter=dest_filter,
                max_trains=limit,
            )
        boards = []
        for station in stations:
            board = {
                "label": station["label"],
                "trains": [],
                "error": fetch_error,
            }
            board = _maybe_enrich_with_razza(
                board,
                station,
                razza_fetch,
                direction,
                dest_filter=dest_filter,
                max_trains=limit,
            )
            boards.append(board)
        return boards

    return {
        "nyc": _build(
            PATH_STATIONS,
            PATH_DIRECTION_NYC,
            _is_nyc_direction,
            None,
            max_trains,
        ),
        "33rd": _build(
            PATH_33RD_STATIONS,
            PATH_DIRECTION_NYC,
            _is_nyc_direction,
            _is_33rd_destination,
            max_33rd_trains,
        ),
        "nj": _build(
            PATH_NJ_STATIONS,
            PATH_DIRECTION_NJ,
            _is_nj_direction,
            None,
            max_trains,
        ),
    }


def get_path_nyc_boards(fetch_json, max_trains=PATH_MAX_TRAINS, panynj_payload=None):
    boards, _payload = _load_boards(
        PATH_STATIONS,
        fetch_json,
        direction=PATH_DIRECTION_NYC,
        direction_filter=_is_nyc_direction,
        max_trains=max_trains,
        panynj_payload=panynj_payload,
    )
    return boards


def get_path_33rd_boards(fetch_json, max_trains=PATH_33RD_MAX_TRAINS, panynj_payload=None):
    boards, _payload = _load_boards(
        PATH_33RD_STATIONS,
        fetch_json,
        direction=PATH_DIRECTION_NYC,
        direction_filter=_is_nyc_direction,
        dest_filter=_is_33rd_destination,
        max_trains=max_trains,
        panynj_payload=panynj_payload,
    )
    return boards


def get_path_nj_boards(fetch_json, max_trains=PATH_MAX_TRAINS, panynj_payload=None):
    boards, _payload = _load_boards(
        PATH_NJ_STATIONS,
        fetch_json,
        direction=PATH_DIRECTION_NJ,
        direction_filter=_is_nj_direction,
        max_trains=max_trains,
        panynj_payload=panynj_payload,
    )
    return boards


def print_path_boards(boards, title="PATH"):
    print(title)
    for board in boards:
        print("")
        print(board["label"])
        if board.get("error"):
            print("  unavailable (%s)" % board["error"])
            continue
        trains = board.get("trains") or []
        if not trains:
            print("  no upcoming trains")
            continue
        for train in trains:
            status = train.get("status")
            suffix = ""
            if status and status not in ("ON_TIME",):
                suffix = " [%s]" % status
            print("  %s -> %s%s" % (train["eta"], train["destination"], suffix))
