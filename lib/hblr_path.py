# -*- coding: utf-8 -*-
"""HBLR ↔ PATH connection tab — four timed transfer pairs."""

from __future__ import annotations

HBLR_PATH_MAX_TRAINS = 3
TRANSIT_TRANSFER_RAW_POOL = 6
HBLR_LSP_EXCHANGE_OFFSET = 11
HBLR_LSP_NEWPORT_OFFSET = 21

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
            "offset": HBLR_LSP_NEWPORT_OFFSET,
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
    note = "%s +%s" % (primary_short, offset)
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
    transit_primary_fetcher=None,
    transit_secondary_fetcher=None,
    fallback_current=False,
    fallback_suffix="PATH",
):
    """Realtime filter, Transit retry for PATH/subway, then live realtime fallback."""
    primary = primary_board

    def _filter(primary_b, secondary_b, *, fallback=False):
        return apply_transfer_filter(
            primary_b,
            secondary_b,
            offset,
            primary_short,
            secondary_short,
            fallback_current=fallback,
            fallback_suffix=fallback_suffix,
        )

    result = _filter(primary, secondary_board)
    if _is_catchable_board(result):
        return result

    from . import transit_app

    if (
        transit_primary_fetcher
        and transit_app.has_api_key()
        and (primary or {}).get("source") != "transit"
    ):
        transit_primary = transit_primary_fetcher()
        if transit_primary:
            result = _filter(transit_primary, secondary_board)
            if _is_catchable_board(result):
                return result
            primary = transit_primary

    if (
        transit_secondary_fetcher
        and transit_app.has_api_key()
        and (secondary_board or {}).get("source") != "transit"
    ):
        transit_secondary = transit_secondary_fetcher()
        if transit_secondary:
            result = _filter(primary, transit_secondary)
            if _is_catchable_board(result):
                return result

    if fallback_current and _is_live_realtime_board(secondary_board):
        return _filter(primary, secondary_board, fallback=True)
    return result


def path_catchable_after_lsp(
    lsp_primary,
    path_board,
    offset,
    path_short,
    *,
    transit_fetcher=None,
):
    """PATH departures catchable after LSP HBLR + offset (PANYNJ, then Transit)."""
    from . import transit_app

    def _filtered(path_b):
        return apply_transfer_filter(
            lsp_primary,
            path_b,
            offset,
            "LSP HBLR",
            path_short,
            fallback_current=False,
        )

    for path_b in (path_board,):
        if not path_b:
            continue
        chained = _filtered(path_b)
        if chained.get("trains"):
            return {
                **path_b,
                "trains": chained["trains"],
                "_raw_trains": chained["trains"],
                "note": chained.get("note"),
            }

    if (
        transit_fetcher
        and transit_app.has_api_key()
        and (path_board or {}).get("source") != "transit"
    ):
        transit_path = transit_fetcher()
        if transit_path:
            chained = _filtered(transit_path)
            if chained.get("trains"):
                return {
                    **transit_path,
                    "trains": chained["trains"],
                    "_raw_trains": chained["trains"],
                    "note": chained.get("note"),
                }

    empty = dict(path_board or {"label": path_short, "trains": []})
    empty["trains"] = []
    empty["note"] = "LSP HBLR +%s" % offset
    return empty


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


def _path_transit_fetcher(spec):
    from lib.path_trains import get_path_transit_board

    def _fetch():
        return get_path_transit_board(
            spec["station"],
            spec["direction"],
            dest_filter=spec.get("dest_filter"),
            max_trains=HBLR_PATH_MAX_TRAINS,
            raw_pool=TRANSIT_TRANSFER_RAW_POOL,
        )

    return _fetch


def get_lsp_primary_board(now=None):
    """Liberty State Park northbound — primary for HBLR → PATH and WTC subway chain."""
    return _hblr_board_for_spec(_LSP_PRIMARY, now=now)


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
    connections = []
    for cfg in _HBLR_TO_PATH_CONNECTIONS:
        secondary_spec = cfg["secondary"]
        secondary_raw = _path_board_for_spec(secondary_spec, path_bundle, fetch_json)
        path_short = secondary_spec["station"].replace(" PATH", "")
        secondary = path_catchable_after_lsp(
            primary,
            secondary_raw,
            secondary_spec["offset"],
            path_short,
            transit_fetcher=_path_transit_fetcher(secondary_spec),
        )
        connections.append(
            {
                "id": cfg["id"],
                "path_label": cfg["path_label"],
                "board": secondary,
            }
        )
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

        secondary = resolve_transfer_board(
            primary,
            secondary_raw,
            secondary_spec["offset"],
            primary_short,
            secondary_short,
            fallback_current=True,
            fallback_suffix="HBLR",
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
