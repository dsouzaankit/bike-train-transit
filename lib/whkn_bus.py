# -*- coding: utf-8 -*-
"""Whkn tab — Lincoln Harbor 156/158/159 → NYC + PABT Fort Lee departures."""

from __future__ import annotations

from .hblr_path import HBLR_PATH_MAX_TRAINS

WHKN_STOP_ID = "21831"
# Transit nearby-stops probe at Lincoln Harbor: NJTB:148700 = stop_code 21831.
WHKN_TRANSIT_STOP_ID = "NJTB:148700"
WHKN_TRANSIT_FALLBACK_STOP_IDS = ("NJTB:148700",)

# Same PABT Transit stop as HOB↔MT; Fort Lee-bound 156/158/159 leave here.
PABT_TRANSIT_STOP_ID = "NJTB:162326"

WHKN_ROUTES = frozenset({"156", "158", "159"})
WHKN_MAX_TRAINS = HBLR_PATH_MAX_TRAINS
TRANSIT_RAW_POOL = 12

SECTION_WHKN = "Whkn · 156/158/159"
WHKN_NYC_DISPLAY = "Lincoln Harbor"
PABT_FORT_LEE_DISPLAY = "PABT → Fort Lee"


def _empty_board(label: str, *, note: str | None = None, error: str | None = None) -> dict:
    return {
        "label": label,
        "trains": [],
        "error": error,
        "note": note,
        "by_line": True,
        "source": "transit",
    }


def _route_in_set(line, routes: frozenset[str]) -> bool:
    text = str(line or "").strip().upper().replace(" ", "")
    if not text:
        return False
    for route in routes:
        if text == route.upper() or text.endswith(route.upper()):
            return True
    return False


def _is_nyc_bus_headsign(headsign) -> bool:
    text = str(headsign or "").casefold()
    return ("new york" in text) or ("nyc" in text) or ("port authority" in text)


def _is_fort_lee_bound_headsign(headsign) -> bool:
    """NJ-bound 156/158/159 leaving PABT — Fort Lee corridor (not into NYC)."""
    if _is_nyc_bus_headsign(headsign):
        return False
    text = str(headsign or "").casefold()
    if not text.strip():
        return False
    hints = (
        "fort lee",
        "englewood",
        "edgewater",
        "cliffside",
        "linwood",
        "med west",
        "park ave",
        "river road",
    )
    return any(hint in text for hint in hints)


def _filter_trains(
    trains,
    *,
    routes: frozenset[str],
    headsign_ok,
    max_trains: int,
) -> list[dict]:
    filtered = [
        train
        for train in trains or []
        if _route_in_set(train.get("line"), routes)
        and headsign_ok(train.get("destination"))
    ]
    return filtered[:max_trains]


def _fetch_filtered_board(
    *,
    label: str,
    transit_stop_ids: tuple[str, ...],
    headsign_ok,
    max_trains: int = WHKN_MAX_TRAINS,
    raw_pool: int = TRANSIT_RAW_POOL,
) -> dict:
    from . import transit_app

    if not transit_app.has_api_key():
        return _empty_board(label, note="no Transit key")

    last_error = None
    for stop_id in transit_stop_ids:
        try:
            payload = transit_app.fetch_stop_departures(
                stop_id,
                max_departures=max(max_trains, raw_pool),
            )
            raw = transit_app.parse_route_departures(
                payload,
                lambda _headsign: True,
                max_trains=max(max_trains, raw_pool),
            )
        except Exception as exc:
            last_error = str(exc)
            continue
        trains = _filter_trains(
            raw,
            routes=WHKN_ROUTES,
            headsign_ok=headsign_ok,
            max_trains=max_trains,
        )
        if trains:
            return {
                "label": label,
                "trains": trains,
                "error": None,
                "by_line": True,
                "source": "transit",
                "note": None,
                "transit_stop_id": stop_id,
            }
    if last_error:
        return _empty_board(label, error=last_error)
    return _empty_board(label, note="no matching departures")


def fetch_whkn_nyc_board(*, max_trains: int = WHKN_MAX_TRAINS) -> dict:
    """156/158/159 at Lincoln Harbor (21831) toward New York."""
    return _fetch_filtered_board(
        label=WHKN_NYC_DISPLAY,
        transit_stop_ids=WHKN_TRANSIT_FALLBACK_STOP_IDS,
        headsign_ok=_is_nyc_bus_headsign,
        max_trains=max_trains,
    )


def fetch_pabt_fort_lee_board(*, max_trains: int = WHKN_MAX_TRAINS) -> dict:
    """156/158/159 leaving PABT toward Fort Lee / Englewood corridor."""
    board = _fetch_filtered_board(
        label=PABT_FORT_LEE_DISPLAY,
        transit_stop_ids=(PABT_TRANSIT_STOP_ID,),
        headsign_ok=_is_fort_lee_bound_headsign,
        max_trains=max_trains,
    )
    try:
        from .pabt_gates import annotate_pabt_board_with_gates

        return annotate_pabt_board_with_gates(board)
    except Exception:
        return board


def build_whkn_sections() -> list[dict]:
    """Ordered UI sections for the Whkn tab."""
    nyc = fetch_whkn_nyc_board()
    pabt = fetch_pabt_fort_lee_board()
    return [{"title": SECTION_WHKN, "boards": [nyc, pabt]}]
