# -*- coding: utf-8 -*-
"""HBLR ↔ PATH connection tab — four timed transfer pairs."""

from __future__ import annotations

HBLR_PATH_MAX_TRAINS = 3

_LSP_PRIMARY = {
    "mode": "hblr",
    "station": "Liberty State Park",
    "direction": "northbound",
}

# Outbound from JC: one LSP primary, two PATH catchment boards.
_HBLR_TO_PATH_CONNECTIONS = (
    {
        "id": "hblr_to_wtc",
        "path_label": "WTC",
        "secondary": {
            "mode": "path",
            "station": "Exchange Place",
            "direction": "nyc",
            "dest_filter": "wtc",
            "offset": 11,
        },
    },
    {
        "id": "hblr_to_33rd",
        "path_label": "33rd St",
        "secondary": {
            "mode": "path",
            "station": "Newport PATH",
            "direction": "nyc_33rd",
            "dest_filter": "33rd",
            "offset": 21,
        },
    },
)

# Inbound to JC: PATH primary + HBLR secondary.
_HBLR_FROM_PATH_SECTIONS = (
    {
        "id": "wtc_to_hblr",
        "title": "PATH WTC → HBLR",
        "primary": {
            "mode": "path",
            "station": "WTC",
            "direction": "nj",
        },
        "secondary": {
            "mode": "hblr",
            "station": "Exchange Place",
            "direction": "to_liberty_state_park",
            "offset": 7,
        },
    },
    {
        "id": "path33_to_hblr",
        "title": "PATH 33rd St → HBLR",
        "primary": {
            "mode": "path",
            "station": "Chris St",
            "direction": "nj",
        },
        "secondary": {
            "mode": "hblr",
            "station": "Newport",
            "direction": "to_liberty_state_park",
            "offset": 13,
        },
    },
)


def _earliest_minutes(board):
    earliest = None
    for train in (board or {}).get("trains") or []:
        minutes = train.get("minutes")
        if minutes is None:
            continue
        if earliest is None or minutes < earliest:
            earliest = minutes
    return earliest


def _is_catchable_board(board):
    note = (board or {}).get("note") or ""
    return bool((board or {}).get("trains")) and "current " not in note


def _is_live_realtime_board(board):
    if not board or board.get("estimated"):
        return False
    source = board.get("source")
    if source in ("pdf",):
        return False
    return True


def apply_transfer_filter(
    primary_board,
    secondary_board,
    offset,
    primary_short,
    secondary_short,
    *,
    fallback_current=False,
    fallback_suffix="PATH",
):
    """Keep secondary departures >= earliest primary + offset."""
    new_board = dict(secondary_board or {"label": secondary_short, "trains": []})
    new_board.setdefault("label", secondary_short)
    primary_min = _earliest_minutes(primary_board)
    if primary_min is None:
        new_board["note"] = "no %s yet" % primary_short
        return new_board
    threshold = primary_min + offset
    source = (secondary_board or {}).get("_raw_trains") or (secondary_board or {}).get("trains") or []
    catchable = [
        train
        for train in source
        if train.get("minutes") is not None and train.get("minutes") >= threshold
    ]
    note = "after %s +%s" % (primary_short, offset)
    if secondary_board and secondary_board.get("estimated"):
        note = "sched · " + note
    if catchable:
        new_board["trains"] = catchable[:HBLR_PATH_MAX_TRAINS]
        new_board["note"] = note
        new_board["error"] = None
    elif fallback_current and source and _is_live_realtime_board(secondary_board):
        current = sorted(
            [train for train in source if train.get("minutes") is not None],
            key=lambda train: train.get("minutes"),
        )[:HBLR_PATH_MAX_TRAINS]
        new_board["trains"] = current
        new_board["note"] = note + " · current %s" % fallback_suffix
        new_board["error"] = None
    else:
        new_board["trains"] = []
        new_board["note"] = note
    return new_board


def resolve_transfer_board(
    primary_board,
    secondary_board,
    offset,
    primary_short,
    secondary_short,
    *,
    secondary_mode="generic",
    hblr_secondary_spec=None,
    fallback_current=False,
    fallback_suffix="PATH",
    now=None,
):
    """Realtime filter, Transit retry for HBLR, then live realtime fallback."""

    def _filter(primary, secondary, *, fallback=False):
        return apply_transfer_filter(
            primary,
            secondary,
            offset,
            primary_short,
            secondary_short,
            fallback_current=fallback,
            fallback_suffix=fallback_suffix,
        )

    result = _filter(primary_board, secondary_board)
    if _is_catchable_board(result):
        return result, primary_board

    from . import transit_app
    from .light_rail import get_hblr_transit_board

    if (
        secondary_mode == "hblr"
        and transit_app.has_api_key()
        and hblr_secondary_spec
        and (secondary_board or {}).get("source") != "transit"
    ):
        transit_secondary = get_hblr_transit_board(
            hblr_secondary_spec["station"],
            hblr_secondary_spec["direction"],
            now=now,
            max_trains=HBLR_PATH_MAX_TRAINS,
            raw_pool=36,
        )
        if transit_secondary:
            result = _filter(primary_board, transit_secondary)
            if _is_catchable_board(result):
                return result, primary_board

    if fallback_current and _is_live_realtime_board(secondary_board):
        return _filter(primary_board, secondary_board, fallback=True), primary_board
    return result, primary_board


def _path_board_for_spec(spec, path_bundle, fetch_json=None):
    from lib.path_trains import get_path_station_board

    station = spec["station"]
    direction = spec["direction"]
    dest = spec.get("dest_filter")
    payload = path_bundle.get("_payload")
    return get_path_station_board(
        station,
        direction,
        dest_filter=dest,
        fetch_json=fetch_json,
        panynj_payload=payload,
        max_trains=HBLR_PATH_MAX_TRAINS,
        raw_pool=12,
    )


def _hblr_board_for_spec(spec, now=None):
    from lib.light_rail import get_hblr_board

    return get_hblr_board(
        spec["station"],
        spec["direction"],
        now=now,
        max_trains=HBLR_PATH_MAX_TRAINS,
        raw_pool=36,
    )


def _build_hblr_to_path_section(path_bundle, fetch_json=None, now=None):
    primary = _hblr_board_for_spec(_LSP_PRIMARY, now=now)

    def _connections_for(primary_board):
        built = []
        for cfg in _HBLR_TO_PATH_CONNECTIONS:
            secondary_spec = cfg["secondary"]
            secondary_raw = _path_board_for_spec(secondary_spec, path_bundle, fetch_json)
            secondary, _ = resolve_transfer_board(
                primary_board,
                secondary_raw,
                secondary_spec["offset"],
                "LSP HBLR",
                secondary_spec["station"].replace(" PATH", ""),
                fallback_current=True,
                fallback_suffix="PATH",
                now=now,
            )
            built.append(
                {
                    "id": cfg["id"],
                    "path_label": cfg["path_label"],
                    "board": secondary,
                }
            )
        return built

    connections = _connections_for(primary)
    if not any(_is_catchable_board(conn["board"]) for conn in connections):
        from . import transit_app
        from .light_rail import get_hblr_transit_board

        if transit_app.has_api_key() and primary.get("source") != "transit":
            transit_primary = get_hblr_transit_board(
                _LSP_PRIMARY["station"],
                _LSP_PRIMARY["direction"],
                now=now,
                max_trains=HBLR_PATH_MAX_TRAINS,
                raw_pool=36,
            )
            if transit_primary:
                upgraded = _connections_for(transit_primary)
                if any(_is_catchable_board(conn["board"]) for conn in upgraded):
                    primary = transit_primary
                    connections = upgraded
    return {
        "id": "hblr_to_path",
        "title": "HBLR → PATH",
        "layout": "shared_primary",
        "primary": primary,
        "connections": connections,
    }


def build_hblr_path_sections(path_bundle, fetch_json=None, now=None):
    """Return UI-ready sections for the HBLR↔PATH tab."""
    sections = [_build_hblr_to_path_section(path_bundle, fetch_json=fetch_json, now=now)]
    for cfg in _HBLR_FROM_PATH_SECTIONS:
        primary_spec = cfg["primary"]
        secondary_spec = cfg["secondary"]

        primary = _path_board_for_spec(primary_spec, path_bundle, fetch_json)
        secondary_raw = _hblr_board_for_spec(secondary_spec, now=now)
        primary_short = primary_spec["station"].replace(" PATH", "")
        secondary_short = secondary_spec["station"] + " HBLR"

        secondary, _primary = resolve_transfer_board(
            primary,
            secondary_raw,
            secondary_spec["offset"],
            primary_short,
            secondary_short,
            secondary_mode="hblr",
            hblr_secondary_spec=secondary_spec,
            fallback_current=True,
            fallback_suffix="HBLR",
            now=now,
        )

        sections.append(
            {
                "id": cfg["id"],
                "title": cfg["title"],
                "primary": primary,
                "secondary": secondary,
            }
        )
    return sections
