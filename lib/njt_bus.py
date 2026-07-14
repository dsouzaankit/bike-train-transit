# -*- coding: utf-8 -*-
"""NJ Transit bus stops for the NJTb tab — Transit App ETAs + MyBus SMS."""

from __future__ import annotations

MYBUS_SMS_NUMBER = "69287"
TRANSIT_RAW_POOL = 12
MAX_TRAINS = 3

# Eastbound first, then westbound — order matches UI.
NJT_BUS_STOPS = (
    {
        "stop_id": "20747",
        "direction": "eastbound",
        "transit_stop_id": "NJTB:183520",
        "display_address": "Grand St / Arlington Ave",
    },
    {
        "stop_id": "30492",
        "direction": "eastbound",
        "transit_stop_id": "NJTB:183522",
        "display_address": "Communipaw Ave / Grand St",
    },
    {
        "stop_id": "20764",
        "direction": "westbound",
        "transit_stop_id": "NJTB:185064",
        "display_address": "Grand St / Marin Blvd",
    },
    {
        "stop_id": "20647",
        "direction": "westbound",
        "transit_stop_id": "NJTB:167898",
        "display_address": "Columbus Dr / Grove St",
    },
)

# Per-stop departure filters on Transit route line + headsign.
#   route 81                    → 20747, 20647
#   route 1 + Exchange|Newark   → 20764, 30492
_ROUTE_81_STOPS = frozenset({"20747", "20647"})
_ROUTE_1_EXCHANGE_NEWARK_STOPS = frozenset({"20764", "30492"})


def stop_spec(stop_id: str) -> dict | None:
    for spec in NJT_BUS_STOPS:
        if spec["stop_id"] == stop_id:
            return spec
    return None


def stop_button_title(stop_id: str) -> str:
    """Street address for the left stop button (stop id is on the ETA card)."""
    spec = stop_spec(stop_id)
    if spec:
        return spec.get("display_address") or stop_id
    return stop_id


def sms_url(stop_id: str) -> str:
    """iOS SMS compose URL: body is the stop id."""
    return "sms:%s&body=%s" % (MYBUS_SMS_NUMBER, stop_id)


def open_mybus_sms(stop_id: str) -> None:
    """Open Messages pre-filled to MyBus (69287) with stop_id; user must tap Send."""
    url = sms_url(stop_id)
    try:
        import shortcuts

        shortcuts.open_url(url)
        return
    except Exception:
        pass
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        pass


def departure_matches_stop(
    stop_id: str, route_line: str | None, headsign: str | None
) -> bool:
    line = str(route_line or "").strip()
    dest = str(headsign or "")
    if stop_id in _ROUTE_81_STOPS:
        return line == "81" and "express" not in dest.casefold()
    if stop_id in _ROUTE_1_EXCHANGE_NEWARK_STOPS:
        return line == "1" and ("Exchange" in dest or "Newark" in dest)
    return False


def empty_board(stop_id: str, *, note: str | None = None) -> dict:
    return {
        "label": stop_id,
        "trains": [],
        "error": None,
        "by_line": True,
        "note": note,
        "source": "transit",
    }


def _filter_transit_trains(stop_id: str, trains: list[dict], *, max_trains: int) -> list[dict]:
    filtered = [
        train
        for train in trains
        if departure_matches_stop(
            stop_id, train.get("line"), train.get("destination")
        )
    ]
    return filtered[:max_trains]


def fetch_transit_board(
    stop_id: str,
    *,
    max_trains: int = MAX_TRAINS,
    raw_pool: int = TRANSIT_RAW_POOL,
) -> dict:
    """Live Transit App departures for one stop. Never raises."""
    from . import transit_app

    spec = stop_spec(stop_id)
    if spec is None:
        return empty_board(stop_id, note="unknown stop")

    transit_stop_id = spec.get("transit_stop_id")
    if not transit_stop_id:
        return empty_board(stop_id, note="no Transit stop")

    if not transit_app.has_api_key():
        return empty_board(stop_id, note="no Transit key")

    try:
        payload = transit_app.fetch_stop_departures(
            transit_stop_id,
            max_departures=max(max_trains, raw_pool),
        )
        raw = transit_app.parse_route_departures(
            payload,
            lambda _headsign: True,
            max_trains=max(max_trains, raw_pool),
        )
    except Exception as exc:
        board = empty_board(stop_id, note=None)
        board["error"] = str(exc)
        return board

    trains = _filter_transit_trains(stop_id, raw, max_trains=max_trains)
    return {
        "label": stop_id,
        "trains": trains,
        "error": None,
        "by_line": True,
        "source": "transit",
        "note": None if trains else "no matching departures",
    }


def fetch_all_transit_boards(
    *,
    max_trains: int = MAX_TRAINS,
    raw_pool: int = TRANSIT_RAW_POOL,
) -> dict[str, dict]:
    """Fetch all NJTb stop boards keyed by stop id."""
    boards = {}
    for spec in NJT_BUS_STOPS:
        stop_id = spec["stop_id"]
        boards[stop_id] = fetch_transit_board(
            stop_id,
            max_trains=max_trains,
            raw_pool=raw_pool,
        )
    return boards


def stops_by_direction() -> list[tuple[str, list[dict]]]:
    """[(direction_title, [stop_spec, ...]), ...] preserving UI order."""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for spec in NJT_BUS_STOPS:
        direction = spec["direction"]
        if direction not in groups:
            groups[direction] = []
            order.append(direction)
        groups[direction].append(spec)
    titles = {"eastbound": "Eastbound", "westbound": "Westbound"}
    return [(titles.get(key, key.title()), groups[key]) for key in order]
