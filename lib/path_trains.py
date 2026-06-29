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

PATH_EXCHANGE_STATION = {
    "slug": "exchange_place",
    "panynj": "EXP",
    "label": "Exchange Place",
}

PATH_33RD_STATIONS = [
    {"slug": "christopher_street", "panynj": "CHR", "label": "Chris St"},
    {"slug": "ninth_street", "panynj": "09S", "label": "9th St"},
]

PATH_14TH_STATION = {
    "slug": "fourteenth_street",
    "panynj": "14S",
    "label": "14 St PATH",
}

NINTH_ST_ESTIMATE_TO_14TH_MINUTES = 1

PATH_NJ_STATIONS = [
    {"slug": "christopher_street", "panynj": "CHR", "label": "Chris St"},
    {"slug": "ninth_street", "panynj": "09S", "label": "9th St"},
    {"slug": "thirty_third_street", "panynj": "33S", "label": "33rd St"},
    # WTC shows Hoboken-bound trains too (transfer point for HBLR via Hoboken).
    {"slug": "world_trade_center", "panynj": "WTC", "label": "WTC", "allow_hoboken": True},
]

_DEST_SHORT = {
    "World Trade Center": "WTC",
    "33rd Street": "33rd St",
    "Journal Square": "JSQ",
    "Hoboken": "Hoboken",
    "Newark": "Newark",
}


def _is_hoboken_destination(name):
    text = (name or "").casefold()
    # "33rd Street via Hoboken" / "Journal Square via Hoboken" are the overnight
    # routings of the 33rd<->JSQ line: they terminate at 33rd/JSQ, not Hoboken.
    if "via hoboken" in text:
        return False
    return "hoboken" in text


def _short_destination(name):
    if not name:
        return "?"
    text = name.strip()
    for full, short in _DEST_SHORT.items():
        if text == full:
            return short
        if text.startswith(full + " "):
            text = short + text[len(full) :]
            break
    return text.replace(" via Hoboken", " via Hob")


def _is_33rd_destination(name):
    text = (name or "").casefold()
    if "world trade" in text or text.strip() == "wtc":
        return False
    return bool(re.search(r"33(?:rd|\s*st)", text))


def _is_wtc_destination(name):
    text = (name or "").casefold()
    return "world trade" in text or text.strip() == "wtc"


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
        match = re.search(r"(\d+)", eta_text)
        if match:
            return "~%sm" % match.group(1)
        return "Delay"
    if minutes is None:
        return "?"
    if minutes <= 0:
        return "Due"
    return "%sm" % minutes


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
        if _is_hoboken_destination(dest):
            continue
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


def _parse_panynj_station(code, payload, direction_filter, dest_filter=None, allow_hoboken=False):
    for result in payload.get("results") or []:
        if result.get("consideredStation") != code:
            continue
        trains = []
        for dest in result.get("destinations") or []:
            if not direction_filter(dest.get("label")):
                continue
            for msg in dest.get("messages") or []:
                headsign = msg.get("headSign") or "?"
                if not allow_hoboken and _is_hoboken_destination(headsign):
                    continue
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
        allow_hoboken=bool(station.get("allow_hoboken")),
    )
    return {
        "label": station["label"],
        "trains": trains[:max_trains],
        "error": None,
    }


# path.api.razza.dev is permanently offline; its SSL handshakes time out (~37s
# per launch) and leave dead sockets that crash Pythonista when GC'd. Disabled.
RAZZA_ENABLED = False


def _maybe_enrich_with_razza(board, station, fetch_json, direction, dest_filter=None, max_trains=PATH_MAX_TRAINS):
    if not RAZZA_ENABLED:
        return board
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


def _load_14th_path_board(fetch_json, panynj_payload=None, max_trains=PATH_33RD_MAX_TRAINS):
    """33rd-bound PATH at 14 St; fallback estimate from 9th St +1 min."""
    payload = panynj_payload
    if payload is None:
        try:
            payload = _fetch_panynj_payload(fetch_json)
        except Exception as exc:
            return {
                "label": PATH_14TH_STATION["label"],
                "trains": [],
                "error": str(exc),
            }

    trains = _parse_panynj_station(
        PATH_14TH_STATION["panynj"],
        payload,
        _is_nyc_direction,
        dest_filter=_is_33rd_destination,
    )
    if trains:
        return {
            "label": PATH_14TH_STATION["label"],
            "trains": trains[:max_trains],
            "error": None,
            "estimated": False,
        }

    ninth = _parse_panynj_station(
        "09S",
        payload,
        _is_nyc_direction,
        dest_filter=_is_33rd_destination,
    )
    if ninth:
        estimated = []
        for train in ninth:
            minutes = train.get("minutes")
            if minutes is not None:
                minutes = minutes + NINTH_ST_ESTIMATE_TO_14TH_MINUTES
            eta_text = train.get("eta")
            if minutes is not None and minutes > 0:
                eta_text = "~%sm" % minutes
            estimated.append(
                {
                    **train,
                    "minutes": minutes,
                    "eta": eta_text,
                    "estimated": True,
                }
            )
        return {
            "label": PATH_14TH_STATION["label"],
            "trains": estimated[:max_trains],
            "error": None,
            "estimated": True,
            "note": "est. 9th St + %s min" % NINTH_ST_ESTIMATE_TO_14TH_MINUTES,
        }

    board = {
        "label": PATH_14TH_STATION["label"],
        "trains": [],
        "error": "No 33rd St trains",
    }
    return _maybe_enrich_with_razza(
        board,
        PATH_14TH_STATION,
        fetch_json,
        PATH_DIRECTION_NYC,
        dest_filter=_is_33rd_destination,
        max_trains=max_trains,
    )


_PATH_STATION_LOOKUP = {}
for _entry in (
    PATH_STATIONS
    + PATH_33RD_STATIONS
    + [PATH_14TH_STATION, PATH_EXCHANGE_STATION]
    + PATH_NJ_STATIONS
):
    _PATH_STATION_LOOKUP[_entry["label"]] = _entry
_PATH_STATION_LOOKUP["Newport"] = _PATH_STATION_LOOKUP["Newport PATH"]


def _dest_filter_fn(name):
    if name == "33rd":
        return _is_33rd_destination
    if name == "wtc":
        return _is_wtc_destination
    return None


def get_path_station_board(
    station_label,
    direction,
    dest_filter=None,
    fetch_json=None,
    panynj_payload=None,
    max_trains=PATH_MAX_TRAINS,
    raw_pool=None,
):
    """Single PATH station board (NYC, 33rd, or NJ). Never raises."""
    station = _PATH_STATION_LOOKUP.get(station_label)
    if station is None:
        return {"label": station_label, "trains": [], "error": "Unknown PATH station"}

    dest_fn = _dest_filter_fn(dest_filter) if isinstance(dest_filter, str) else dest_filter
    pool = raw_pool or max(max_trains, PATH_MAX_TRAINS)

    if direction == "nyc":
        dir_filter = _is_nyc_direction
        path_direction = PATH_DIRECTION_NYC
    elif direction == "nyc_33rd":
        dir_filter = _is_nyc_direction
        path_direction = PATH_DIRECTION_NYC
        dest_fn = dest_fn or _is_33rd_destination
    elif direction == "nj":
        dir_filter = _is_nj_direction
        path_direction = PATH_DIRECTION_NJ
    else:
        return {"label": station_label, "trains": [], "error": "Unknown direction"}

    payload = panynj_payload
    error = None
    if payload is None and fetch_json is not None:
        try:
            payload = _fetch_panynj_payload(fetch_json)
        except Exception as exc:
            error = str(exc)

    trains = []
    if payload is not None:
        trains = _parse_panynj_station(
            station["panynj"],
            payload,
            dir_filter,
            dest_filter=dest_fn,
            allow_hoboken=bool(station.get("allow_hoboken")),
        )
    board = {
        "label": station["label"],
        "trains": trains[:max_trains],
        "_raw_trains": trains,
        "error": error if not trains else None,
    }
    if not trains and fetch_json is not None:
        board = _maybe_enrich_with_razza(
            board,
            station,
            fetch_json,
            path_direction,
            dest_filter=dest_fn,
            max_trains=max_trains,
        )
        if board.get("trains"):
            board["_raw_trains"] = board["trains"]
    return board


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

    path_33rd = _build(
        PATH_33RD_STATIONS,
        PATH_DIRECTION_NYC,
        _is_nyc_direction,
        _is_33rd_destination,
        max_33rd_trains,
    )
    path_14th = _load_14th_path_board(
        razza_fetch,
        panynj_payload=payload,
        max_trains=max_33rd_trains,
    )
    if path_14th.get("trains"):
        path_33rd = [path_14th] + path_33rd

    bundle = {
        "nyc": _build(
            PATH_STATIONS,
            PATH_DIRECTION_NYC,
            _is_nyc_direction,
            None,
            max_trains,
        ),
        "33rd": path_33rd,
        "nj": _build(
            PATH_NJ_STATIONS,
            PATH_DIRECTION_NJ,
            _is_nj_direction,
            None,
            max_trains,
        ),
        "_payload": payload,
    }
    return bundle


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
    boards, payload = _load_boards(
        PATH_33RD_STATIONS,
        fetch_json,
        direction=PATH_DIRECTION_NYC,
        direction_filter=_is_nyc_direction,
        dest_filter=_is_33rd_destination,
        max_trains=max_trains,
        panynj_payload=panynj_payload,
    )
    fourteenth = _load_14th_path_board(
        fetch_json,
        panynj_payload=payload or panynj_payload,
        max_trains=max_trains,
    )
    if fourteenth.get("trains"):
        boards = [fourteenth] + boards
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
