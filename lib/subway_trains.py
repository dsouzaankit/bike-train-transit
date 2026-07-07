# -*- coding: utf-8 -*-
"""NYC subway departures — north/Queens and downtown toward JC."""

import re
import urllib.parse
from lib.parallel import map_parallel, run_parallel
from lib.subway_lines import line_sort_key, normalize_line

SUBWAY_API_BASE = "https://subwayinfo.nyc/api/arrivals"
SUBWAY_DIRECTION_NORTH = "N"
SUBWAY_DIRECTION_SOUTH = "S"
SUBWAY_FETCH_LIMIT = 20
CANAL_WTC_ESTIMATE_MINUTES = 2
TO_JC_ETAS_PER_LINE = 2

EXCHANGE_WTC_PATH_WALK = 8

# Subway station -> (PATH 33rd board label, walk minutes from PATH platform).
SUBWAY_PATH_WALKS = {
    "Chris St": ("Chris St", 5),
    "West 4 St": ("9 St", 5),
    "6 Av": ("14 St", 2),
    "14 St - Union Sq": ("14 St", 6),
}

NORTH_SUBWAY_ORDER = (
    "Chris St",
    "West 4 St",
    "6 Av",
    "14 St - Union Sq",
    "51 St",
    "50 St",
    "Bleecker St",
)

SUBWAY_STATIONS_NORTH = [
    {"station_id": "133", "label": "Chris St", "direction": SUBWAY_DIRECTION_NORTH},
    {"station_id": ["A32", "D20"], "label": "West 4 St", "direction": SUBWAY_DIRECTION_NORTH},
]

SUBWAY_FIFTY_FIRST = {
    "station_id": "630",
    "label": "51 St",
    "direction": SUBWAY_DIRECTION_NORTH,
}

SUBWAY_FIFTY_ST = {
    "station_id": "A25",
    "label": "50 St",
    "direction": SUBWAY_DIRECTION_NORTH,
}

SUBWAY_BLEECKER = {
    "station_id": "637",
    "label": "Bleecker St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

FIFTY_FIRST_LINE_SPECS = (
    ("4", SUBWAY_DIRECTION_NORTH),
    ("5", SUBWAY_DIRECTION_NORTH),
)

FIFTY_ST_LINE_SPECS = (("A", SUBWAY_DIRECTION_NORTH),)

BLEECKER_LINE_SPECS = (
    ("4", SUBWAY_DIRECTION_SOUTH),
    ("5", SUBWAY_DIRECTION_SOUTH),
)

SUBWAY_WTC_CORTLANDT = {
    "station_id": "138",
    "label": "WTC Cortlandt",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_WTC_CORTLANDT_NORTH = {
    "station_id": "138",
    "label": "WTC Cortlandt",
    "direction": SUBWAY_DIRECTION_NORTH,
    "transit_stop_id": "MTAS:19443",
}

SUBWAY_WTC_E = {
    "station_id": "E01",
    "label": "WTC",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_WTC_E_NORTH = {
    "station_id": "E01",
    "label": "WTC",
    "direction": SUBWAY_DIRECTION_NORTH,
    "transit_stop_id": "MTAS:19012",
}

WTC_CORTLANDT_NORTH_LINE_SPECS = (("1", SUBWAY_DIRECTION_NORTH),)
WTC_E_NORTH_LINE_SPECS = (
    ("A", SUBWAY_DIRECTION_NORTH),
    ("C", SUBWAY_DIRECTION_NORTH),
    ("E", SUBWAY_DIRECTION_NORTH),
)

WTC_E_SOUTH_LINE_SPECS = (("E", SUBWAY_DIRECTION_SOUTH),)
WTC_CORTLANDT_SOUTH_LINE_SPECS = (("1", SUBWAY_DIRECTION_SOUTH),)
WEST_4_SOUTH_LINE_SPECS = (
    ("E", SUBWAY_DIRECTION_SOUTH),
    ("F", SUBWAY_DIRECTION_SOUTH),
)
CHRIS_SOUTH_LINE_SPECS = (("1", SUBWAY_DIRECTION_SOUTH),)
FIFTY_ST_2_SOUTH_LINE_SPECS = (("2", SUBWAY_DIRECTION_SOUTH),)
FIFTY_ST_AC_SOUTH_LINE_SPECS = (
    ("A", SUBWAY_DIRECTION_SOUTH),
    ("C", SUBWAY_DIRECTION_SOUTH),
)

SUBWAY_CHRIS_SOUTH = {
    "station_id": "133",
    "label": "Chris St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_FIFTY_ST_7AV_SOUTH = {
    "station_id": "125",
    "label": "50 St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_FIFTY_ST_8AV_SOUTH = {
    "station_id": "A25",
    "label": "50 St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_LEX_53_SOUTH = {
    "station_id": "F11",
    "label": "Lex/53 St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

FIFTY_ST_8AV_SOUTH_LINE_SPECS = (
    ("E", SUBWAY_DIRECTION_SOUTH),
    ("F", SUBWAY_DIRECTION_SOUTH),
)
FIFTY_ST_7AV_SOUTH_LINE_SPECS = (
    ("1", SUBWAY_DIRECTION_SOUTH),
    ("F", SUBWAY_DIRECTION_SOUTH),
)
LEX_53_SOUTH_LINE_SPECS = (
    ("E", SUBWAY_DIRECTION_SOUTH),
    ("1", SUBWAY_DIRECTION_SOUTH),
    ("F", SUBWAY_DIRECTION_SOUTH),
)

SUBWAY_WEST_4_SOUTH = {
    "station_id": ["A32", "D20"],
    "label": "West 4 St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_CANAL_ACE = {
    "station_id": "A34",
    "label": "Canal St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_SIXTH_AV_L = {
    "station_id": "L02",
    "label": "6 Av",
    "direction": SUBWAY_DIRECTION_SOUTH,
}

SUBWAY_UNION_SQ = {
    "station_id": "635",
    "label": "14 St - Union Sq",
}

# (line, direction) pairs shown on the Union Sq card.
UNION_SQ_LINE_SPECS = (
    ("4", SUBWAY_DIRECTION_NORTH),
    ("5", SUBWAY_DIRECTION_NORTH),
    ("6", SUBWAY_DIRECTION_NORTH),
    ("6", SUBWAY_DIRECTION_SOUTH),
)

_HEADSIGN_SHORT = {
    "Van Cortlandt Park-242 St": "Van Cortlandt",
    "Inwood-207 St": "Inwood",
    "168 St": "168 St",
    "Jamaica Center": "Jamaica",
    "Jamaica-179 St": "Jamaica",
    "Norwood-205 St": "Norwood",
    "South Ferry": "South Ferry",
    "World Trade Center": "WTC",
    "Canarsie-Rockaway Pkwy": "Canarsie",
    "Pelham Bay Park": "Pelham",
    "Eastchester-Dyre Av": "Eastchester",
    "Woodlawn": "Woodlawn",
    "Brooklyn Bridge-City Hall": "Bk Bridge",
    "Parkchester": "Parkchester",
}


def _short_headsign(name, *, truncate=True):
    if not name:
        return "?"
    text = str(name).strip()
    if text in _HEADSIGN_SHORT:
        return _HEADSIGN_SHORT[text]
    if "-242 St" in text:
        return text.split("-", 1)[0]
    if truncate and len(text) > 18:
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
        "direction": item.get("direction"),
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


def _is_downtown_subway_headsign(headsign):
    """Southbound trains toward downtown / Brooklyn / South Ferry (MT→JC)."""
    text = (headsign or "").casefold()
    if not text:
        return True
    uptown_hints = (
        "uptown",
        "bronx",
        "van cortlandt",
        "inwood",
        "woodlawn",
        "241 st",
        "242 st",
        "207 st",
        "fordham",
        "pelham",
        "dyre",
        "norwood",
        "wakefield",
    )
    if any(hint in text for hint in uptown_hints):
        return False
    downtown_hints = (
        "downtown",
        "brooklyn",
        "south ferry",
        "world trade",
        "wtc",
        "canarsie",
        "flatbush",
        "stillwell",
        "coney",
        "new lots",
        "bk bridge",
        "borough hall",
        "euclid",
    )
    return any(hint in text for hint in downtown_hints)


def _is_brooklyn_l_headsign(headsign):
    text = (headsign or "").casefold()
    return "canarsie" in text or "rockaway" in text


def fetch_station_arrivals(
    station,
    fetch_json,
    limit=6,
    headsign_filter=None,
    extra_minutes=0,
    estimated=False,
):
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

    out = []
    for item in arrivals:
        norm = _normalize_arrival(item, extra_minutes=extra_minutes, estimated=estimated)
        if norm is not None:
            out.append(norm)
    out.sort(key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999)
    return out


def format_train_eta(train):
    """Display ETA; ↓ suffix for southbound 6 (Union Sq) and 4/5 (Bleecker St)."""
    eta = str(train.get("eta") or "?")
    if train.get("direction") == SUBWAY_DIRECTION_SOUTH and normalize_line(
        train.get("line")
    ) in ("6", "4", "5"):
        return eta + "\u2193"
    return eta


def _sort_by_eta(trains):
    return sorted(
        trains or [],
        key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999,
    )


def _trains_per_line(arrivals, line_specs=None, per_line=1):
    """Keep up to per_line soonest trains for each line (and direction when specified)."""
    buckets = {}
    for train in arrivals or []:
        line = normalize_line(train.get("line"))
        if line == "?":
            continue
        direction = train.get("direction")
        if line_specs is not None:
            matched = any(
                normalize_line(spec_line) == line
                and (spec_dir is None or spec_dir == direction)
                for spec_line, spec_dir in line_specs
            )
            if not matched:
                continue
            key = "%s:%s" % (line, direction or "?")
        else:
            key = line
        buckets.setdefault(key, []).append(train)

    for key in buckets:
        buckets[key].sort(
            key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999
        )

    result = []
    if line_specs is not None:
        for spec_line, spec_dir in line_specs:
            key = "%s:%s" % (normalize_line(spec_line), spec_dir or "?")
            result.extend(buckets.get(key, [])[:per_line])
        return _sort_by_eta(result)

    for line_key in sorted(buckets.keys(), key=lambda k: line_sort_key(k.split(":")[0])):
        result.extend(buckets[line_key][:per_line])
    return _sort_by_eta(result)


def _earliest_per_line(arrivals, line_specs=None):
    return _trains_per_line(arrivals, line_specs=line_specs, per_line=1)


def _express_lines_from_specs(line_specs):
    return {normalize_line(line) for line, _direction in (line_specs or ())}


def _annotate_express_local_board(board, line_specs):
    """Note when express trains stop at a station that is normally local-only."""
    express = _express_lines_from_specs(line_specs)
    raw = board.get("_raw_trains") or []
    express_trains = board.get("trains") or []
    local_lines = sorted(
        {
            normalize_line(train.get("line"))
            for train in raw
            if normalize_line(train.get("line")) not in express
            and normalize_line(train.get("line")) != "?"
        }
    )

    board["express_local"] = True
    if express_trains:
        board["note"] = "Express local stop"
    elif local_lines:
        board["note"] = "Express skip · local %s" % "/".join(local_lines)
        board["empty_hint"] = "Express not stopping"
    else:
        board["note"] = "Express not stopping"
        board["empty_hint"] = "Express not stopping"
    return board


def _load_express_local_board(
    station,
    fetch_json,
    *,
    line_specs,
    fetch_limit=SUBWAY_FETCH_LIMIT,
    per_line=1,
):
    board = _load_line_board(
        station,
        fetch_json,
        line_specs=line_specs,
        fetch_limit=fetch_limit,
        per_line=per_line,
    )
    return _annotate_express_local_board(board, line_specs)


def _load_line_board(
    station,
    fetch_json,
    *,
    line_specs=None,
    headsign_filter=None,
    extra_minutes=0,
    estimated=False,
    fetch_limit=SUBWAY_FETCH_LIMIT,
    per_line=1,
):
    error = None
    trains = []
    raw = []
    try:
        raw = fetch_station_arrivals(
            station,
            fetch_json,
            limit=fetch_limit,
            headsign_filter=headsign_filter,
            extra_minutes=extra_minutes,
            estimated=estimated,
        )
        trains = _trains_per_line(raw, line_specs=line_specs, per_line=per_line)
        if line_specs is not None:
            raw = _trains_per_line(raw, line_specs=line_specs, per_line=fetch_limit)
    except Exception as exc:
        error = str(exc)
    board = {
        "label": station["label"],
        "trains": trains,
        "by_line": True,
        "error": error if not trains else None,
        "_raw_trains": raw,
        "_line_specs": line_specs,
        "_per_line": per_line,
        "source": "subwayapi" if raw else None,
    }
    if extra_minutes and trains:
        board["estimated"] = estimated
    return board


def _load_world_trade_center_board(fetch_json, per_line=TO_JC_ETAS_PER_LINE):
    error = None
    try:
        trains = fetch_station_arrivals(SUBWAY_WTC_E, fetch_json, limit=SUBWAY_FETCH_LIMIT)
        trains = _trains_per_line(trains, per_line=per_line)
        if trains:
            return {
                "label": SUBWAY_WTC_E["label"],
                "trains": trains,
                "by_line": True,
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
            limit=SUBWAY_FETCH_LIMIT,
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
        trains = _trains_per_line(raw, per_line=per_line)
        if trains:
            return {
                "label": SUBWAY_WTC_E["label"],
                "trains": trains,
                "by_line": True,
                "error": None,
                "estimated": True,
                "note": "est. Canal St + %s min" % CANAL_WTC_ESTIMATE_MINUTES,
            }
    except Exception as exc:
        if error is None:
            error = str(exc)

    return {
        "label": SUBWAY_WTC_E["label"],
        "trains": [],
        "by_line": True,
        "error": error or "No WTC-bound trains",
        "estimated": False,
    }


def _load_union_sq_board(fetch_json, per_line=1):
    error = None
    merged = []
    try:
        for spec_line, spec_dir in UNION_SQ_LINE_SPECS:
            station = {
                **SUBWAY_UNION_SQ,
                "direction": spec_dir,
            }
            for train in fetch_station_arrivals(
                station,
                fetch_json,
                limit=SUBWAY_FETCH_LIMIT,
            ):
                if normalize_line(train.get("line")) != normalize_line(spec_line):
                    continue
                if train.get("direction") != spec_dir:
                    continue
                merged.append(train)
        trains = _trains_per_line(merged, line_specs=UNION_SQ_LINE_SPECS, per_line=per_line)
        return {
            "label": SUBWAY_UNION_SQ["label"],
            "trains": trains,
            "by_line": True,
            "error": None if trains else "No matching trains",
            "_raw_trains": merged,
            "_line_specs": UNION_SQ_LINE_SPECS,
            "_per_line": per_line,
        }
    except Exception as exc:
        error = str(exc)
    return {
        "label": SUBWAY_UNION_SQ["label"],
        "trains": [],
        "by_line": True,
        "error": error,
        "_raw_trains": [],
        "_line_specs": UNION_SQ_LINE_SPECS,
        "_per_line": per_line,
    }


def _path_arrival_minutes(path_board):
    earliest = None
    for train in (path_board or {}).get("trains") or []:
        minutes = train.get("minutes")
        if minutes is None:
            continue
        if earliest is None or minutes < earliest:
            earliest = minutes
    return earliest


def apply_path_subway_connections(subway_boards, path_33rd_boards):
    """Drop subway trains that depart before PATH arrival + walk at the paired station."""
    path_by_label = {b.get("label"): b for b in path_33rd_boards or []}
    connected = []
    for board in subway_boards or []:
        label = board.get("label")
        pairing = SUBWAY_PATH_WALKS.get(label)
        if pairing is None:
            connected.append(board)
            continue

        path_label, walk = pairing
        path_min = _path_arrival_minutes(path_by_label.get(path_label))
        if path_min is None:
            note = "no %s PATH yet" % path_label.replace(" PATH", "")
            if label == "6 Av":
                note = "L East/Bk · " + note
            new_board = dict(board)
            new_board["note"] = note
            connected.append(new_board)
            continue

        threshold = path_min + walk
        source = board.get("_raw_trains") or board.get("trains") or []
        filtered = [
            train
            for train in source
            if train.get("minutes") is not None and train.get("minutes") >= threshold
        ]
        line_specs = board.get("_line_specs")
        per_line = board.get("_per_line", 1)
        if line_specs is not None:
            catchable = _trains_per_line(filtered, line_specs=line_specs, per_line=per_line)
        else:
            catchable = _trains_per_line(filtered, per_line=per_line)

        short_path = path_label.replace(" PATH", "")
        note = "PATH %s +%s" % (short_path, walk)
        if label == "6 Av":
            note = "L East/Bk · " + note
        new_board = dict(board)
        new_board["note"] = note
        new_board["trains"] = catchable
        if catchable:
            new_board["error"] = None
        connected.append(new_board)
    return connected


def _is_uptown_subway_headsign(headsign):
    text = (headsign or "").casefold()
    if _is_south_ferry_headsign(headsign):
        return False
    downtown_hints = (
        "downtown",
        "brooklyn",
        "euclid",
        "stillwell",
        "flatbush",
        "new lots",
        "canarsie",
    )
    return not any(hint in text for hint in downtown_hints)


def get_subway_transit_board(station, *, max_trains=3, raw_pool=8, per_line=1):
    """Transit App subway departures — deeper pool for HBLR-tab transfer filters."""
    from . import transit_app
    from .hblr_path import TRANSIT_TRANSFER_RAW_POOL

    if not transit_app.has_api_key():
        return None
    stop_id = station.get("transit_stop_id")
    if not stop_id:
        return None
    cap = TRANSIT_TRANSFER_RAW_POOL
    pool = max(max_trains, min(cap, raw_pool))
    line_specs = None
    label = station.get("label")
    if label == "WTC Cortlandt":
        line_specs = list(WTC_CORTLANDT_NORTH_LINE_SPECS)
    elif label == "WTC":
        line_specs = list(WTC_E_NORTH_LINE_SPECS)
    try:
        payload = transit_app.fetch_stop_departures(stop_id, max_departures=pool)
        raw = transit_app.parse_route_departures(
            payload,
            _is_uptown_subway_headsign,
            max_trains=pool,
        )
        for train in raw:
            train["direction"] = SUBWAY_DIRECTION_NORTH
            line = normalize_line(train.get("line"))
            if line not in (None, "", "?"):
                train["line"] = line
    except Exception:
        return None
    if not raw:
        return None
    filtered_pool = _trains_per_line(raw, line_specs=line_specs, per_line=pool)
    trains = _trains_per_line(filtered_pool, line_specs=line_specs, per_line=per_line)
    return {
        "label": station["label"],
        "trains": trains[:max_trains],
        "_raw_trains": filtered_pool,
        "by_line": True,
        "error": None,
        "source": "transit",
        "_line_specs": line_specs,
        "_per_line": per_line,
    }


def _path_primary_after_lsp(lsp_primary, path_board):
    """Exchange PATH WTC departures catchable after LSP HBLR + offset."""
    from lib.hblr_path import (
        HBLR_LSP_EXCHANGE_OFFSET,
        path_catchable_after_lsp,
    )
    from lib.path_trains import get_path_transit_board

    return path_catchable_after_lsp(
        lsp_primary,
        path_board,
        HBLR_LSP_EXCHANGE_OFFSET,
        "Exchange",
        transit_fetcher=lambda: get_path_transit_board(
            "Exchange Place",
            "nyc",
            dest_filter="wtc",
            max_trains=3,
            raw_pool=8,
        ),
    )


def apply_exchange_wtc_subway_connections(path_board, subway_boards, lsp_primary=None):
    """Northbound WTC subway cards after LSP → Exchange PATH + walk."""
    from lib.hblr_path import (
        HBLR_LSP_EXCHANGE_OFFSET,
        TRANSIT_TRANSFER_RAW_POOL,
        resolve_transfer_board,
    )
    from lib.path_trains import get_path_transit_board

    path_primary = (
        _path_primary_after_lsp(lsp_primary, path_board) if lsp_primary else path_board
    )
    lsp_note = (
        "LSP HBLR +%s · " % HBLR_LSP_EXCHANGE_OFFSET if lsp_primary else ""
    )

    connected = []
    for board in subway_boards or []:
        label = board.get("label")
        station = SUBWAY_WTC_CORTLANDT_NORTH if label == "WTC Cortlandt" else SUBWAY_WTC_E_NORTH
        if lsp_primary and not path_primary.get("trains"):
            empty = dict(board)
            empty["trains"] = []
            empty["note"] = lsp_note + "no Exchange yet"
            connected.append(empty)
            continue
        path_transit_fetcher = None
        if not lsp_primary:
            path_transit_fetcher = lambda: get_path_transit_board(
                "Exchange Place",
                "nyc",
                dest_filter="wtc",
                max_trains=3,
                raw_pool=TRANSIT_TRANSFER_RAW_POOL,
            )
        allow_fallback = not lsp_primary or bool(path_primary.get("trains"))
        filtered = resolve_transfer_board(
            path_primary,
            board,
            EXCHANGE_WTC_PATH_WALK,
            "Exchange",
            board.get("label", "Subway"),
            transit_primary_fetcher=path_transit_fetcher,
            transit_secondary_fetcher=lambda st=station: get_subway_transit_board(st),
            fallback_current=allow_fallback,
            fallback_suffix="subway",
        )
        if lsp_note and filtered.get("note"):
            filtered["note"] = lsp_note + filtered["note"]
        connected.append(filtered)
    return connected


def get_wtc_north_boards(fetch_json):
    """Uptown subway at WTC Cortlandt (1) and WTC (A/C/E)."""

    def _cortlandt():
        return _load_line_board(
            SUBWAY_WTC_CORTLANDT_NORTH,
            fetch_json,
            line_specs=WTC_CORTLANDT_NORTH_LINE_SPECS,
            headsign_filter=_is_uptown_subway_headsign,
            fetch_limit=SUBWAY_FETCH_LIMIT,
        )

    def _wtc():
        return _load_line_board(
            SUBWAY_WTC_E_NORTH,
            fetch_json,
            line_specs=WTC_E_NORTH_LINE_SPECS,
            headsign_filter=_is_uptown_subway_headsign,
            fetch_limit=SUBWAY_FETCH_LIMIT,
        )

    boards = []
    results = run_parallel({"cortlandt": _cortlandt, "wtc": _wtc})
    if results.get("cortlandt") is not None:
        boards.append(results["cortlandt"])
    if results.get("wtc") is not None:
        boards.append(results["wtc"])
    return boards


def _load_sixth_av_l_board(fetch_json, per_line=1):
    board = _load_line_board(
        SUBWAY_SIXTH_AV_L,
        fetch_json,
        line_specs=(("L", SUBWAY_DIRECTION_SOUTH),),
        headsign_filter=_is_brooklyn_l_headsign,
        fetch_limit=SUBWAY_FETCH_LIMIT,
        per_line=per_line,
    )
    board["note"] = "L East/Bk"
    return board


def get_subway_north_boards(fetch_json):
    by_label = {}

    def _load_board(station):
        return _load_line_board(
            station,
            fetch_json,
            fetch_limit=SUBWAY_FETCH_LIMIT,
        )

    for board in map_parallel(SUBWAY_STATIONS_NORTH, _load_board):
        if board is not None:
            by_label[board["label"]] = board

    by_label["6 Av"] = _load_sixth_av_l_board(fetch_json)
    by_label["14 St - Union Sq"] = _load_union_sq_board(fetch_json)
    by_label["51 St"] = _load_express_local_board(
        SUBWAY_FIFTY_FIRST,
        fetch_json,
        line_specs=FIFTY_FIRST_LINE_SPECS,
        fetch_limit=SUBWAY_FETCH_LIMIT,
    )
    by_label["50 St"] = _load_express_local_board(
        SUBWAY_FIFTY_ST,
        fetch_json,
        line_specs=FIFTY_ST_LINE_SPECS,
        fetch_limit=SUBWAY_FETCH_LIMIT,
    )
    by_label["Bleecker St"] = _load_express_local_board(
        SUBWAY_BLEECKER,
        fetch_json,
        line_specs=BLEECKER_LINE_SPECS,
        fetch_limit=SUBWAY_FETCH_LIMIT,
    )

    boards = []
    for label in NORTH_SUBWAY_ORDER:
        if label in by_label:
            boards.append(by_label[label])
    return boards


def get_subway_to_jc_boards(fetch_json):
    boards = []
    per_line = TO_JC_ETAS_PER_LINE

    def _cortlandt():
        board = _load_line_board(
            SUBWAY_WTC_CORTLANDT,
            fetch_json,
            headsign_filter=_is_south_ferry_headsign,
            fetch_limit=SUBWAY_FETCH_LIMIT,
            per_line=per_line,
        )
        if not board.get("trains") and not board.get("error"):
            board["note"] = "No South Ferry 1"
        return board

    results = run_parallel(
        {
            "cortlandt": _cortlandt,
            "wtc": lambda: _load_world_trade_center_board(fetch_json, per_line=per_line),
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
            print("  %s  %s -> %s" % (format_train_eta(train), train["line"], train["destination"]))
