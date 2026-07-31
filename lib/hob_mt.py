# -*- coding: utf-8 -*-
"""HOB↔MT tab — NJT bus, subway catchable after Lincoln, NY Waterway, MTA bus.

Offset model (subway catchable):
  Primary = LincTnl → NYC (minutes from Tunnels tab; 0 if unknown).
  Plan notation ``+4+<NY-Lincoln-eta>`` means chain from LincTnl with walk +4
  (card note: ``LincTnl +4``), not a synthetic now-offset of 4+lincoln.
  E/C/A/4/5 use +4; 7 uses +4+5; 6 uses +4+8.
  MTA bus M42/M50 is chained from NY Waterway +15.
  fallback_current=True when catchable filter misses.
"""

from __future__ import annotations

from lib.hblr_path import (
    HBLR_PATH_MAX_TRAINS,
    apply_transfer_filter,
    resolve_transfer_board,
)
from lib.subway_trains import (
    FIFTY_FIRST_LINE_SPECS,
    FIFTY_ST_LINE_SPECS,
    SUBWAY_DIRECTION_NORTH,
    SUBWAY_DIRECTION_SOUTH,
    SUBWAY_FETCH_LIMIT,
    SUBWAY_FIFTY_FIRST,
    SUBWAY_FIFTY_ST,
    _is_uptown_subway_headsign,
    _load_express_local_board,
    _load_line_board,
    _trains_per_line,
    fetch_station_arrivals,
)
from lib.subway_lines import normalize_line
from lib.tunnel_crossings import get_tunnel_boards

# --- Offsets (exported for tests) ---
HOB_MT_WALK_OFFSET = 4
HOB_MT_SEVEN_EXTRA = 5
HOB_MT_SIX_EXTRA = 8
HOB_MT_MTA_BUS_OFFSET = 15
HOB_MT_MAX_TRAINS = HBLR_PATH_MAX_TRAINS
TRANSIT_RAW_POOL = 12

# --- Section titles (order) ---
SECTION_NJT_BUS = "NJT bus → NYC"
SECTION_PABT = "PABT departures"
# Hoboken Terminal 126 + HBLR share one section so they paint side-by-side.
SECTION_HOB_TERMINAL = "Hoboken Terminal · HBLR"
# Willow + PABT share one section so they paint side-by-side.
SECTION_NJT_PABT = "NJT bus · PABT dep"
SECTION_SUBWAY = "Subway catchable"
SECTION_NYWATERWAY = "NY Waterway"
SECTION_MTA_BUS = "MTA bus catchable"
# Last ferry + bus boards share one section so they paint side-by-side.
SECTION_FERRY_BUS = "NY Waterway · MTA bus"
HOB_MT_SECTION_TITLES = (
    SECTION_HOB_TERMINAL,
    SECTION_NJT_PABT,
    SECTION_SUBWAY,
    SECTION_FERRY_BUS,
)

# --- Hoboken Bus Terminal (stop #20496), route 126 toward NYC ---
HOB_BUS_STOP_ID = "20496"
HOB_BUS_DISPLAY = "Hoboken Terminal"
HOB_BUS_TRANSIT_STOP_ID = "NJTB:148699"
HOB_BUS_ROUTES = frozenset({"126"})

# --- Hoboken HBLR → Tonnelle Av (Transit NJTR:3080 / stop_code 30829) ---
HOB_HBLR_STATION = "Hoboken"
HOB_HBLR_DISPLAY = "Hoboken HBLR"

# --- NJT Willow Ave + 15th (stop #32084), routes 126/119 toward NYC ---
NJT_WILLOW_STOP_ID = "32084"
NJT_WILLOW_DISPLAY = "Willow Ave + 15th St"
# Transit nearby-stops probe around Willow/15th:
# - NJTB:162273 reliably returns 119/126 toward New York.
# - keep nearby variants as fallback ids.
NJT_WILLOW_TRANSIT_STOP_ID = "NJTB:162273"
NJT_WILLOW_TRANSIT_FALLBACK_STOP_IDS = (
    "NJTB:162274",
    "NJTB:32084",
)
NJT_WILLOW_ROUTES = frozenset({"126", "119"})

# --- PABT departures (buses leaving Port Authority toward NJ) ---
PABT_ROUTES = frozenset({"126", "119", "123"})
# Transit nearby-stops probe: NJTB:162326 serves 119/123/126 leaving PABT.
PABT_TRANSIT_STOP_ID = "NJTB:162326"
PABT_DISPLAY = "PABT dep"

# --- Subway stations (subwayinfo.nyc / GTFS ids) ---
SUBWAY_PABT_ACE = {
    "station_id": "A27",
    "label": "42 St-PABT",
    "direction": SUBWAY_DIRECTION_NORTH,
}
PABT_EC_LINE_SPECS = (
    ("E", SUBWAY_DIRECTION_NORTH),
    ("C", SUBWAY_DIRECTION_NORTH),
)

SUBWAY_TIMES_SQ_7 = {
    "station_id": "725",
    "label": "Times Sq-42 St (7)",
    "direction": SUBWAY_DIRECTION_NORTH,
}
TIMES_SQ_7_LINE_SPECS = (("7", SUBWAY_DIRECTION_NORTH),)

SUBWAY_GRAND_CENTRAL_6 = {
    "station_id": "631",
    "label": "Grand Central-42 St",
}
GRAND_CENTRAL_6_LINE_SPECS = (
    ("6", SUBWAY_DIRECTION_NORTH),
    ("6", SUBWAY_DIRECTION_SOUTH),
)

# Lexington local 33 St (GTFS 632). Note: 634 is 23 St, not 33 St.
SUBWAY_THIRTY_THIRD_LEX = {
    "station_id": "632",
    "label": "33 St",
    "direction": SUBWAY_DIRECTION_SOUTH,
}
THIRTY_THIRD_LINE_SPECS = (
    ("4", SUBWAY_DIRECTION_SOUTH),
    ("5", SUBWAY_DIRECTION_SOUTH),
)

# --- NY Waterway (Hoboken 14th → Midtown / W39th) ---
NYWATERWAY_PLATFORM = 9
NYWATERWAY_ETA_PAGE = "https://etacloud.connexionz.net/nywaterway/eta/9"
NYWATERWAY_LABEL = "Hoboken 14th St"
NYWATERWAY_TRANSIT_STOP_ID = "NYW:596"
# Connexionz JSON candidates — first successful parse wins.
NYWATERWAY_ETA_URLS = (
    "https://etacloud.connexionz.net/rtt/public/command/get_stop_eta?platformNo=9",
    "https://eta.connexionz.net/rtt/public/command/get_stop_eta?platformNo=9",
    "https://etacloud.connexionz.net/nywaterway/rtt/public/command/get_stop_eta?platformNo=9",
)

# --- MTA bus M42/M50 near 12 Av / W 42 St (Plus Code QX6X+XG) ---
MTA_BUS_STOP_DISPLAY = "12 Av / W 42 St"
MTA_BUS_PLUS_CODE = "QX6X+XG"
MTA_BUS_ROUTES = frozenset({"M42", "M50"})
# Transit nearby-stops probe around 12 Av/W 42:
# - MTAMNT:15430 includes both M42 and M50.
# - fallback ids are nearby variants that may carry one direction/feed variant.
MTA_BUS_TRANSIT_STOP_ID = "MTAMNT:15430"
MTA_BUS_TRANSIT_FALLBACK_STOP_IDS = (
    "MTAMNT:12223",
    "MTAMNT:12384",
    "MTAMNT:15329",
)


def subway_base_offset(lincoln_nyc_minutes: int | None = None) -> int:
    """Walk after LincTnl (Lincoln ETA lives on the primary board, not here)."""
    return HOB_MT_WALK_OFFSET


def seven_transfer_offset(base_offset: int) -> int:
    return int(base_offset) + HOB_MT_SEVEN_EXTRA


def six_transfer_offset(base_offset: int) -> int:
    return int(base_offset) + HOB_MT_SIX_EXTRA


def extract_lincoln_nyc_minutes(tunnel_boards) -> int | None:
    """NY-bound Lincoln Tunnel minutes from get_tunnel_boards() result."""
    for board in tunnel_boards or []:
        if (board or {}).get("label") != "Lincoln Tunnel":
            continue
        for row in board.get("trains") or []:
            dest = (row.get("destination") or "").strip()
            if dest in ("→ NYC", "ToNY") or "nyc" in dest.casefold():
                minutes = row.get("minutes")
                if minutes is None:
                    return None
                try:
                    return int(minutes)
                except (TypeError, ValueError):
                    return None
    return None


def resolve_lincoln_nyc_minutes(
    *,
    tunnel_boards_cached=None,
    fetch_transit_payload=None,
) -> int | None:
    """Cached Tunnels-tab data first; else PANYNJ crossing-times (JSON array)."""
    lincoln = extract_lincoln_nyc_minutes(tunnel_boards_cached or [])
    if lincoln is not None:
        return lincoln
    if fetch_transit_payload is None:
        return None
    try:
        tunnel_boards = get_tunnel_boards(fetch_transit_payload)
        return extract_lincoln_nyc_minutes(tunnel_boards)
    except Exception:
        return None


def _empty_board(label: str, *, note: str | None = None, error: str | None = None) -> dict:
    return {
        "label": label,
        "trains": [],
        "error": error,
        "by_line": True,
        "note": note,
    }


def _has_minutes(board: dict | None) -> bool:
    for train in (board or {}).get("trains") or []:
        if train.get("minutes") is not None:
            return True
    return False


def _is_queens_bound_headsign(headsign) -> bool:
    text = (headsign or "").casefold()
    if not text:
        return False
    queens_hints = (
        "jamaica",
        "flushing",
        "queens",
        "forest hills",
        "briarwood",
        "kew gardens",
        "court sq",
        "mets-",
        "main st",
    )
    return any(hint in text for hint in queens_hints)


def _is_pabt_e_or_c_headsign(headsign) -> bool:
    """E toward Queens or C northbound/uptown."""
    if _is_queens_bound_headsign(headsign):
        return True
    return _is_uptown_subway_headsign(headsign)


def _is_nyc_bus_headsign(headsign) -> bool:
    text = str(headsign or "").casefold()
    return ("new york" in text) or ("nyc" in text) or ("port authority" in text)


def _is_pabt_departure_headsign(headsign) -> bool:
    """Buses leaving PABT toward NJ — exclude NYC-bound (into-terminal) signs."""
    if _is_nyc_bus_headsign(headsign):
        return False
    return bool(str(headsign or "").strip())


def _route_in_set(line, routes: frozenset[str]) -> bool:
    text = str(line or "").strip().upper().replace(" ", "")
    if not text:
        return False
    for route in routes:
        if text == route.upper() or text.endswith(route.upper()):
            return True
    return False


def _is_nyw_midtown_headsign(headsign) -> bool:
    text = (headsign or "").casefold()
    if not text:
        return False
    return ("midtown" in text) or ("w. 39" in text) or ("w 39" in text)


def _filter_route_trains(trains, routes: frozenset[str], *, max_trains: int) -> list[dict]:
    filtered = [
        train
        for train in trains or []
        if _route_in_set(train.get("line"), routes)
    ]
    return filtered[:max_trains]


def make_lincoln_primary_board(lincoln_nyc_minutes: int | None) -> dict:
    """Synthetic Lincoln→NYC board shown on the subway section."""
    mins = 0 if lincoln_nyc_minutes is None else int(lincoln_nyc_minutes)
    eta = "Due" if mins <= 0 else "%sm" % mins
    note = None
    if lincoln_nyc_minutes is None:
        note = "LincTnl ETA unknown · using 0"
    return {
        "label": "LincTnl → NYC",
        "trains": [
            {
                "minutes": mins,
                "eta": eta,
                "destination": "→ NYC",
                "status": "ON_TIME",
            }
        ],
        "error": None,
        "note": note,
        "source": "panynj-crossingtimes",
        "by_line": False,
    }


def fetch_hoboken_126_board(*, fetch_transit_json=None) -> dict:
    """NJT 126 at Hoboken Bus Terminal toward NYC via Transit App. Never raises."""
    from . import transit_app

    label = HOB_BUS_DISPLAY
    if not transit_app.has_api_key():
        return _empty_board(label, note="no Transit key")
    try:
        payload = transit_app.fetch_stop_departures(
            HOB_BUS_TRANSIT_STOP_ID,
            max_departures=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
        )
        raw = transit_app.parse_route_departures(
            payload,
            lambda _headsign: True,
            max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
        )
    except Exception as exc:
        board = _empty_board(label, error=str(exc))
        board["source"] = "transit"
        return board
    filtered = _filter_route_trains(
        raw, HOB_BUS_ROUTES, max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL)
    )
    trains = [
        train
        for train in filtered
        if _is_nyc_bus_headsign(train.get("destination"))
    ][:HOB_MT_MAX_TRAINS]
    if not trains:
        board = _empty_board(label, note="no 126 to NYC")
        board["source"] = "transit"
        return board
    return {
        "label": label,
        "trains": trains,
        "error": None,
        "by_line": True,
        "source": "transit",
        "note": None,
    }


def fetch_hoboken_hblr_tonnelle_board() -> dict:
    """HBLR at Hoboken Terminal toward Tonnelle Av. Never raises."""
    from lib.light_rail import get_hblr_board

    board = get_hblr_board(
        HOB_HBLR_STATION,
        "northbound",
        max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
        raw_pool=TRANSIT_RAW_POOL,
    )
    raw = list(board.get("_raw_trains") or board.get("trains") or [])
    trains = [
        train
        for train in raw
        if "tonnelle" in str(train.get("destination") or "").casefold()
    ][:HOB_MT_MAX_TRAINS]
    out = {
        "label": HOB_HBLR_DISPLAY,
        "trains": trains,
        "error": board.get("error"),
        "by_line": True,
        "source": board.get("source"),
        "note": board.get("note"),
    }
    if board.get("estimated"):
        out["estimated"] = True
    if not trains:
        if out.get("error"):
            return out
        out["note"] = out.get("note") or "no HBLR to Tonnelle"
        out["trains"] = []
    return out


def fetch_njt_willow_board(*, fetch_transit_json=None) -> dict:
    """NJT 126/119 at Willow Ave + 15th via Transit App. Never raises."""
    from . import transit_app

    label = NJT_WILLOW_DISPLAY
    if not transit_app.has_api_key():
        return _empty_board(label, note="no Transit key")
    stop_ids = (NJT_WILLOW_TRANSIT_STOP_ID,) + NJT_WILLOW_TRANSIT_FALLBACK_STOP_IDS
    last_error = None
    used_stop_id = NJT_WILLOW_TRANSIT_STOP_ID
    trains = []
    for stop_id in stop_ids:
        try:
            payload = transit_app.fetch_stop_departures(
                stop_id,
                max_departures=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
            )
            raw = transit_app.parse_route_departures(
                payload,
                lambda _headsign: True,
                max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
            )
            filtered = _filter_route_trains(
                raw, NJT_WILLOW_ROUTES, max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL)
            )
            filtered = [
                train for train in filtered if _is_nyc_bus_headsign(train.get("destination"))
            ]
            if filtered:
                used_stop_id = stop_id
                trains = filtered[:HOB_MT_MAX_TRAINS]
                break
        except Exception as exc:
            last_error = str(exc)
            continue
    if not trains and last_error:
        board = _empty_board(label, note=None)
        board["error"] = last_error
        return board
    return {
        "label": label,
        "trains": trains,
        "error": None,
        "by_line": True,
        "source": "transit",
        "note": None if trains else "no 126/119 to NYC",
    }


def fetch_pabt_board(*, fetch_transit_json=None) -> dict:
    """PABT 126/119/123 *departures* leaving the terminal (Transit stop_departures)."""
    from . import transit_app

    label = PABT_DISPLAY
    if not transit_app.has_api_key():
        board = _empty_board(label, note="no Transit key")
        board["source"] = "transit"
        return board
    try:
        payload = transit_app.fetch_stop_departures(
            PABT_TRANSIT_STOP_ID,
            max_departures=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
        )
        raw = transit_app.parse_route_departures(
            payload,
            _is_pabt_departure_headsign,
            max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
        )
    except Exception as exc:
        board = _empty_board(label, error=str(exc))
        board["source"] = "transit"
        return board
    trains = _filter_route_trains(raw, PABT_ROUTES, max_trains=HOB_MT_MAX_TRAINS)
    if not trains:
        board = _empty_board(label, note="no 126/119/123 dep")
        board["source"] = "transit"
        return board
    return {
        "label": label,
        "trains": trains,
        "error": None,
        "by_line": True,
        "source": "transit",
        "note": None,
    }


def _load_grand_central_6_board(fetch_json) -> dict:
    error = None
    merged = []
    try:
        for _line, spec_dir in GRAND_CENTRAL_6_LINE_SPECS:
            station = {**SUBWAY_GRAND_CENTRAL_6, "direction": spec_dir}
            for train in fetch_station_arrivals(
                station,
                fetch_json,
                limit=SUBWAY_FETCH_LIMIT,
            ):
                if normalize_line(train.get("line")) != "6":
                    continue
                if train.get("direction") != spec_dir:
                    continue
                merged.append(train)
        trains = _trains_per_line(
            merged, line_specs=GRAND_CENTRAL_6_LINE_SPECS, per_line=1
        )
        return {
            "label": SUBWAY_GRAND_CENTRAL_6["label"],
            "trains": trains,
            "by_line": True,
            "error": None if trains else "No matching trains",
            "_raw_trains": _trains_per_line(
                merged, line_specs=GRAND_CENTRAL_6_LINE_SPECS, per_line=SUBWAY_FETCH_LIMIT
            ),
            "_line_specs": GRAND_CENTRAL_6_LINE_SPECS,
            "_per_line": 1,
            "source": "subwayapi" if merged else None,
        }
    except Exception as exc:
        error = str(exc)
    return {
        "label": SUBWAY_GRAND_CENTRAL_6["label"],
        "trains": [],
        "by_line": True,
        "error": error,
        "_raw_trains": [],
        "_line_specs": GRAND_CENTRAL_6_LINE_SPECS,
        "_per_line": 1,
    }


def _filter_catchable(
    lincoln_primary,
    secondary,
    offset,
    secondary_short,
    *,
    fallback_current: bool,
):
    return resolve_transfer_board(
        lincoln_primary,
        secondary,
        offset,
        "LincTnl",
        secondary_short,
        fallback_current=fallback_current,
        fallback_suffix="subway",
    )


def build_subway_catchable_boards(fetch_json, *, lincoln_nyc_minutes: int | None) -> list[dict]:
    """LincTnl primary + catchable subway boards after +4 / +4+5 / +4+8."""
    base = subway_base_offset()
    fallback_current = True
    lincoln_primary = make_lincoln_primary_board(lincoln_nyc_minutes)
    boards = [lincoln_primary]

    try:
        e_c_raw = _load_line_board(
            SUBWAY_PABT_ACE,
            fetch_json,
            line_specs=PABT_EC_LINE_SPECS,
            headsign_filter=_is_pabt_e_or_c_headsign,
            fetch_limit=SUBWAY_FETCH_LIMIT,
            per_line=1,
        )
        boards.append(
            _filter_catchable(
                lincoln_primary,
                e_c_raw,
                base,
                e_c_raw.get("label") or "42 St-PABT",
                fallback_current=fallback_current,
            )
        )
    except Exception as exc:
        boards.append(_empty_board("42 St-PABT", error=str(exc)))

    try:
        seven_raw = _load_line_board(
            SUBWAY_TIMES_SQ_7,
            fetch_json,
            line_specs=TIMES_SQ_7_LINE_SPECS,
            headsign_filter=_is_queens_bound_headsign,
            fetch_limit=SUBWAY_FETCH_LIMIT,
            per_line=1,
        )
        boards.append(
            _filter_catchable(
                lincoln_primary,
                seven_raw,
                seven_transfer_offset(base),
                seven_raw.get("label") or "7",
                fallback_current=fallback_current,
            )
        )
    except Exception as exc:
        boards.append(_empty_board("Times Sq-42 St (7)", error=str(exc)))

    try:
        a_raw = _load_express_local_board(
            SUBWAY_FIFTY_ST,
            fetch_json,
            line_specs=FIFTY_ST_LINE_SPECS,
            fetch_limit=SUBWAY_FETCH_LIMIT,
        )
        # Prefer uptown/north A only (station already direction N).
        boards.append(
            _filter_catchable(
                lincoln_primary,
                a_raw,
                base,
                a_raw.get("label") or "50 St",
                fallback_current=fallback_current,
            )
        )
    except Exception as exc:
        boards.append(_empty_board("50 St", error=str(exc)))

    try:
        six_raw = _load_grand_central_6_board(fetch_json)
        boards.append(
            _filter_catchable(
                lincoln_primary,
                six_raw,
                six_transfer_offset(base),
                six_raw.get("label") or "Grand Central",
                fallback_current=fallback_current,
            )
        )
    except Exception as exc:
        boards.append(_empty_board("Grand Central-42 St", error=str(exc)))

    try:
        lex51 = _load_express_local_board(
            SUBWAY_FIFTY_FIRST,
            fetch_json,
            line_specs=FIFTY_FIRST_LINE_SPECS,
            fetch_limit=SUBWAY_FETCH_LIMIT,
        )
        boards.append(
            _filter_catchable(
                lincoln_primary,
                lex51,
                base,
                lex51.get("label") or "51 St",
                fallback_current=fallback_current,
            )
        )
    except Exception as exc:
        boards.append(_empty_board("51 St", error=str(exc)))

    try:
        lex33 = _load_line_board(
            SUBWAY_THIRTY_THIRD_LEX,
            fetch_json,
            line_specs=THIRTY_THIRD_LINE_SPECS,
            fetch_limit=SUBWAY_FETCH_LIMIT,
            per_line=1,
        )
        boards.append(
            _filter_catchable(
                lincoln_primary,
                lex33,
                base,
                lex33.get("label") or "33 St",
                fallback_current=fallback_current,
            )
        )
    except Exception as exc:
        boards.append(_empty_board("33 St", error=str(exc)))

    return boards


def _parse_nywaterway_payload(payload) -> list[dict]:
    """Best-effort flatten Connexionz-ish JSON into train rows."""
    trains = []
    if payload is None:
        return trains
    # Common shapes: list of etas, or {stop/etas/...}, or nested route groups.
    candidates = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for key in ("etas", "ETA", "Etas", "departures", "trips", "Trips", "platforms"):
            val = payload.get(key)
            if isinstance(val, list):
                candidates = val
                break
        if not candidates:
            stop = payload.get("stop") or payload.get("Stop") or {}
            if isinstance(stop, dict):
                for key in ("etas", "ETA", "Etas", "destination"):
                    val = stop.get(key)
                    if isinstance(val, list):
                        candidates = val
                        break
            route = payload.get("route") or payload.get("Route")
            if isinstance(route, list):
                for group in route:
                    if not isinstance(group, dict):
                        continue
                    dest = group.get("destinationName") or group.get("DestinationName") or "Midtown"
                    for trip in group.get("trip") or group.get("Trip") or []:
                        if isinstance(trip, dict):
                            trip = dict(trip)
                            trip.setdefault("destination", dest)
                            candidates.append(trip)

    for item in candidates:
        if not isinstance(item, dict):
            continue
        minutes = item.get("minutes")
        if minutes is None:
            minutes = item.get("ETA") or item.get("eta") or item.get("Minutes")
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            # Connexionz sometimes returns \"Due\" / \"1 min\"
            text = str(minutes or "").strip().casefold()
            if text in ("due", "arriving", "0"):
                minutes = 0
            else:
                digits = "".join(ch for ch in text if ch.isdigit())
                if not digits:
                    continue
                minutes = int(digits)
        dest = (
            item.get("destination")
            or item.get("DestinationName")
            or item.get("destinationName")
            or item.get("TripName")
            or "Midtown / W39th"
        )
        eta = "Due" if minutes <= 0 else "%sm" % minutes
        trains.append(
            {
                "minutes": minutes,
                "eta": eta,
                "destination": str(dest),
                "line": "NYW",
                "status": "ON_TIME",
            }
        )
    trains.sort(key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999)
    return trains[:HOB_MT_MAX_TRAINS]


def fetch_nywaterway_board(fetch_json) -> dict:
    """Hoboken 14th → Midtown/W39th. Never raises; empty + note if API unavailable."""
    from . import transit_app

    label = NYWATERWAY_LABEL
    last_error = None

    # Prefer Transit API: this is currently the most reliable live source.
    if transit_app.has_api_key():
        try:
            payload = transit_app.fetch_stop_departures(
                NYWATERWAY_TRANSIT_STOP_ID,
                max_departures=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
            )
            trains = transit_app.parse_route_departures(
                payload,
                _is_nyw_midtown_headsign,
                max_trains=HOB_MT_MAX_TRAINS,
            )
            if trains:
                return {
                    "label": label,
                    "trains": trains,
                    "error": None,
                    "by_line": True,
                    "source": "transit",
                    "note": None,
                }
            last_error = "no Midtown departures in Transit feed"
        except Exception as exc:
            last_error = str(exc)

    # Fallback to Connexionz parser for compatibility.
    for url in NYWATERWAY_ETA_URLS:
        try:
            payload = fetch_json(url)
            trains = _parse_nywaterway_payload(payload)
            if trains:
                return {
                    "label": label,
                    "trains": trains,
                    "error": None,
                    "by_line": False,
                    "source": "connexionz",
                    "note": None,
                }
            if payload is not None:
                last_error = "unparsed Connexionz payload"
        except Exception as exc:
            last_error = str(exc)
            continue
    return _empty_board(
        label,
        note="ETA source unavailable",
        error=last_error,
    )


def fetch_mta_bus_board(*, fetch_transit_json=None) -> dict:
    """M42/M50 at 12 Av/W 42 St via Transit App. Empty + note if unavailable."""
    from . import transit_app

    label = MTA_BUS_STOP_DISPLAY
    if not transit_app.has_api_key():
        return _empty_board(
            label,
            note="M42/M50 · no Transit key",
        )
    stop_ids = (MTA_BUS_TRANSIT_STOP_ID,) + MTA_BUS_TRANSIT_FALLBACK_STOP_IDS
    raw = []
    used_stop_id = MTA_BUS_TRANSIT_STOP_ID
    last_error = None
    for stop_id in stop_ids:
        try:
            payload = transit_app.fetch_stop_departures(
                stop_id,
                max_departures=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
            )
            raw = transit_app.parse_route_departures(
                payload,
                lambda _headsign: True,
                max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
            )
            trains_try = _filter_route_trains(
                raw,
                MTA_BUS_ROUTES,
                max_trains=max(HOB_MT_MAX_TRAINS, TRANSIT_RAW_POOL),
            )
            if trains_try:
                used_stop_id = stop_id
                trains = trains_try
                break
        except Exception as exc:
            last_error = str(exc)
            continue
    else:
        trains = []
        if last_error:
            return _empty_board(
                label,
                note="M42/M50 unavailable",
                error=last_error,
            )
    if not trains:
        return _empty_board(
            label,
            note="no M42/M50",
        )
    return {
        "label": label,
        "trains": trains,
        "error": None,
        "by_line": True,
        "source": "transit",
        "_raw_trains": trains,
        "note": None,
    }


def build_hob_mt_sections(
    fetch_json,
    *,
    fetch_transit_json=None,
    fetch_transit_payload=None,
    tunnel_boards_cached=None,
) -> list[dict]:
    """Return ordered UI sections for HOB↔MT tab.

    Each section: {"title": str, "boards": [board, ...]}
    board shape matches TransitCard: label, trains[{minutes,eta,destination,line?...}], note, error, by_line?
    """
    sections: list[dict] = []

    # 1. Hoboken Terminal 126 → NYC + HBLR → Tonnelle (side-by-side)
    try:
        hob_bus_board = fetch_hoboken_126_board(fetch_transit_json=fetch_transit_json)
    except Exception as exc:
        hob_bus_board = _empty_board(HOB_BUS_DISPLAY, error=str(exc))
    try:
        hob_hblr_board = fetch_hoboken_hblr_tonnelle_board()
    except Exception as exc:
        hob_hblr_board = _empty_board(HOB_HBLR_DISPLAY, error=str(exc))
    sections.append(
        {"title": SECTION_HOB_TERMINAL, "boards": [hob_bus_board, hob_hblr_board]}
    )

    # 2. NJT Willow → NYC + PABT departures (side-by-side)
    try:
        njt_board = fetch_njt_willow_board(fetch_transit_json=fetch_transit_json)
    except Exception as exc:
        njt_board = _empty_board(NJT_WILLOW_DISPLAY, error=str(exc))
    try:
        pabt_board = fetch_pabt_board(fetch_transit_json=fetch_transit_json)
    except Exception as exc:
        pabt_board = _empty_board(PABT_DISPLAY, error=str(exc))
    sections.append(
        {"title": SECTION_NJT_PABT, "boards": [njt_board, pabt_board]}
    )

    # 3. Subway catchable
    # Prefer already-rendered Tunnels-tab data to keep HOB↔MT consistent with UI.
    # crossingtimesapi.json is a JSON array — must use fetch_transit_payload, not fetch_json.
    lincoln = resolve_lincoln_nyc_minutes(
        tunnel_boards_cached=tunnel_boards_cached,
        fetch_transit_payload=fetch_transit_payload,
    )
    try:
        subway_boards = build_subway_catchable_boards(
            fetch_json, lincoln_nyc_minutes=lincoln
        )
    except Exception as exc:
        subway_boards = [
            make_lincoln_primary_board(lincoln),
            _empty_board("Subway", error=str(exc)),
        ]
    sections.append({"title": SECTION_SUBWAY, "boards": subway_boards})

    # 4. NY Waterway + MTA bus catchable (+15) — side-by-side in one section
    try:
        nyw_board = fetch_nywaterway_board(fetch_json)
    except Exception as exc:
        nyw_board = _empty_board(
            NYWATERWAY_LABEL,
            note="ETA source unavailable",
            error=str(exc),
        )
    try:
        mta_raw = fetch_mta_bus_board(fetch_transit_json=fetch_transit_json)
        if _has_minutes(nyw_board):
            mta_board = resolve_transfer_board(
                nyw_board,
                mta_raw,
                HOB_MT_MTA_BUS_OFFSET,
                "NYW",
                mta_raw.get("label") or MTA_BUS_STOP_DISPLAY,
                fallback_current=True,
                fallback_suffix="bus",
            )
        else:
            # If NY Waterway is unavailable, show current realtime M42/M50 instead of empty.
            mta_board = dict(mta_raw)
            mta_board["note"] = "NYW unavailable · current bus"
    except Exception as exc:
        mta_board = _empty_board(MTA_BUS_STOP_DISPLAY, error=str(exc))
    sections.append(
        {"title": SECTION_FERRY_BUS, "boards": [nyw_board, mta_board]}
    )

    return sections
