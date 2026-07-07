# -*- coding: utf-8 -*-
"""MT → JC tab — uptown subway → PATH (Nwk/JSQ/Hoboken) → HBLR southbound."""

from __future__ import annotations

from datetime import datetime

from lib.hblr_path import (
    HBLR_PATH_MAX_TRAINS,
    TRANSIT_TRANSFER_RAW_POOL,
    resolve_transfer_board,
)
from lib.light_rail import get_hblr_board, get_hblr_transit_board
from lib.path_trains import get_path_station_board, get_path_transit_board
from lib.subway_lines import normalize_line
from lib.subway_trains import (
    CHRIS_SOUTH_LINE_SPECS,
    FIFTY_ST_2_SOUTH_LINE_SPECS,
    FIFTY_ST_AC_SOUTH_LINE_SPECS,
    FIFTY_ST_7AV_SOUTH_LINE_SPECS,
    FIFTY_ST_8AV_SOUTH_LINE_SPECS,
    LEX_53_SOUTH_LINE_SPECS,
    SUBWAY_CHRIS_SOUTH,
    SUBWAY_FETCH_LIMIT,
    SUBWAY_FIFTY_ST_7AV_SOUTH,
    SUBWAY_FIFTY_ST_8AV_SOUTH,
    SUBWAY_LEX_53_SOUTH,
    SUBWAY_WEST_4_SOUTH,
    SUBWAY_WTC_CORTLANDT,
    SUBWAY_WTC_E,
    WEST_4_SOUTH_LINE_SPECS,
    WTC_CORTLANDT_SOUTH_LINE_SPECS,
    WTC_E_SOUTH_LINE_SPECS,
    _is_downtown_subway_headsign,
    _is_south_ferry_headsign,
    _load_line_board,
    _trains_per_line,
)

MT_TO_JC_MAX_TRAINS = HBLR_PATH_MAX_TRAINS
MT_PATH_RAW_POOL = max(12, TRANSIT_TRANSFER_RAW_POOL)
MT_HBLR_RAW_POOL = 36

# Row subway cards (uptown / shuttle origins).
MT_SUBWAY_SOURCES = {
    "50_8av": {
        "label": "50 St (8Av)",
        "station": SUBWAY_FIFTY_ST_8AV_SOUTH,
        "line_specs": FIFTY_ST_8AV_SOUTH_LINE_SPECS,
        "headsign_filter": _is_downtown_subway_headsign,
        "f_line": True,
        "unavailable_note": "No downtown E",
    },
    "50_7av": {
        "label": "50 St (7Av)",
        "station": SUBWAY_FIFTY_ST_7AV_SOUTH,
        "line_specs": FIFTY_ST_7AV_SOUTH_LINE_SPECS,
        "headsign_filter": _is_downtown_subway_headsign,
        "f_line": True,
        "unavailable_note": "No downtown 1",
    },
    "lex_53": {
        "label": "Lex/53 St",
        "station": SUBWAY_LEX_53_SOUTH,
        "line_specs": LEX_53_SOUTH_LINE_SPECS,
        "headsign_filter": _is_downtown_subway_headsign,
        "f_line": True,
        "unavailable_note": "No downtown E/1/F",
    },
    "50_st_2": {
        "label": "50 St (2)",
        "station": SUBWAY_FIFTY_ST_7AV_SOUTH,
        "line_specs": FIFTY_ST_2_SOUTH_LINE_SPECS,
        "headsign_filter": _is_downtown_subway_headsign,
        "unavailable_note": "No downtown 2",
    },
    "50_st_ac": {
        "label": "50 St (A/C)",
        "station": SUBWAY_FIFTY_ST_8AV_SOUTH,
        "line_specs": FIFTY_ST_AC_SOUTH_LINE_SPECS,
        "headsign_filter": _is_downtown_subway_headsign,
        "unavailable_note": "No downtown A/C",
    },
}

# Downtown monitors — gate PATH legs when southbound service is unavailable.
MT_DOWNTOWN_GATES = {
    "wtc_e": {
        "label": "WTC",
        "station": SUBWAY_WTC_E,
        "line_specs": WTC_E_SOUTH_LINE_SPECS,
        "unavailable_note": "No downtown E",
    },
    "wtc_cortlandt": {
        "label": "WTC Cortlandt",
        "station": SUBWAY_WTC_CORTLANDT,
        "line_specs": WTC_CORTLANDT_SOUTH_LINE_SPECS,
        "headsign_filter": _is_south_ferry_headsign,
        "unavailable_note": "No South Ferry 1",
    },
    "west_4": {
        "label": "West 4 St",
        "station": SUBWAY_WEST_4_SOUTH,
        "line_specs": WEST_4_SOUTH_LINE_SPECS,
        "headsign_filter": _is_downtown_subway_headsign,
        "f_line": True,
        "unavailable_note": "No downtown E/F",
    },
    "chris_st": {
        "label": "Chris St",
        "station": SUBWAY_CHRIS_SOUTH,
        "line_specs": CHRIS_SOUTH_LINE_SPECS,
        "headsign_filter": _is_downtown_subway_headsign,
        "unavailable_note": "No downtown 1",
    },
}

# PATH station -> downtown gate key(s); any gate with southbound trains opens the leg.
MT_ROW_PATH_GATES = {
    "mt_50_8av": {
        "9 St": ("west_4",),
        "WTC": ("wtc_e",),
    },
    "mt_50_7av": {
        "Chris St": ("chris_st",),
        "WTC": ("wtc_cortlandt",),
    },
    "mt_lex_53": {
        "9 St": ("west_4",),
        "WTC": ("wtc_e",),
    },
    "mt_50_st_2": {
        "Chris St": ("chris_st",),
    },
    "mt_50_st_ac": {
        "9 St": ("west_4",),
    },
}

MT_TO_JC_ROWS = (
    {
        "id": "mt_50_8av",
        "subway_key": "50_8av",
        "path_primary": {"station": "9 St", "offset": 15},
        "path_wtc_offset": 19,
        "hblr_newport_offset": 14,
        "hblr_exchange_offset": 7,
        "include_wtc_path": True,
    },
    {
        "id": "mt_50_7av",
        "subway_key": "50_7av",
        "path_primary": {"station": "Chris St", "offset": 15},
        "path_wtc_offset": 20,
        "hblr_newport_offset": 13,
        "hblr_exchange_offset": 7,
        "include_wtc_path": True,
    },
    {
        "id": "mt_lex_53",
        "subway_key": "lex_53",
        "path_primary": {"station": "9 St", "offset": 20},
        "path_wtc_offset": 25,
        "hblr_newport_offset": 14,
        "hblr_exchange_offset": 7,
        "include_wtc_path": True,
    },
    {
        "id": "mt_50_st_2",
        "subway_key": "50_st_2",
        "path_primary": {"station": "Chris St", "offset": 15},
        "hblr_newport_offset": 13,
        "include_wtc_path": False,
    },
    {
        "id": "mt_50_st_ac",
        "subway_key": "50_st_ac",
        "path_primary": {"station": "9 St", "offset": 15},
        "hblr_newport_offset": 14,
        "include_wtc_path": False,
    },
)


def f_line_active(now=None):
    """F line on row/gate cards: Mon–Fri 6:00 AM – 9:30 PM."""
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    clock = now.hour * 60 + now.minute
    return 6 * 60 <= clock < 21 * 60 + 30


def _earliest_minutes(board):
    earliest = None
    for train in (board or {}).get("trains") or []:
        minutes = train.get("minutes")
        if minutes is None:
            continue
        if earliest is None or minutes < earliest:
            earliest = minutes
    return earliest


def _subway_available(subway):
    return _earliest_minutes(subway) is not None


def _gate_on_subway(subway, board, dep_label):
    """Keep PATH/HBLR empty when the row subway has no southbound departures."""
    if _subway_available(subway):
        return board
    out = dict(board or {"label": dep_label, "trains": []})
    out["trains"] = []
    out["note"] = "no %s yet" % subway.get("label", "subway")
    out["error"] = None
    return out


def _load_subway_source(source_key, sources, fetch_json, now=None):
    now = now or datetime.now()
    source = sources[source_key]
    station = {**source["station"], "label": source["label"]}
    line_specs = source.get("line_specs")
    board = _load_line_board(
        station,
        fetch_json,
        line_specs=line_specs,
        headsign_filter=source.get("headsign_filter"),
        fetch_limit=SUBWAY_FETCH_LIMIT,
        per_line=1,
    )

    if source.get("f_line") and not f_line_active(now):
        raw_before = board.get("_raw_trains") or []
        had_f = any(
            normalize_line(train.get("line")) == "F" for train in raw_before
        )
        merged = [
            train
            for train in raw_before
            if normalize_line(train.get("line")) != "F"
        ]
        trains = _trains_per_line(merged, line_specs=line_specs, per_line=1)
        board["trains"] = trains
        board["_raw_trains"] = _trains_per_line(
            merged, line_specs=line_specs, per_line=SUBWAY_FETCH_LIMIT
        )
        if had_f:
            board["note"] = "F wkdys 6a–9:30p"
        board["error"] = None if trains else board.get("error")

    if not board.get("trains"):
        note = source.get("unavailable_note")
        if note:
            board["note"] = note
        board["error"] = None

    board["unavailable"] = not _subway_available(board)
    return board


def _load_mt_subway_board(source_key, fetch_json, now=None):
    return _load_subway_source(source_key, MT_SUBWAY_SOURCES, fetch_json, now=now)


def _load_downtown_gates(fetch_json, now=None):
    return {
        key: _load_subway_source(key, MT_DOWNTOWN_GATES, fetch_json, now=now)
        for key in MT_DOWNTOWN_GATES
    }


def _downtown_gate_open(gate_keys, downtown_boards):
    return any(
        _subway_available(downtown_boards.get(key) or {})
        for key in gate_keys
    )


def _gate_path_on_downtown(path_board, path_station, row_id, downtown_boards):
    """Clear PATH when downtown southbound monitor(s) for that leg are empty."""
    gate_keys = (MT_ROW_PATH_GATES.get(row_id) or {}).get(path_station)
    if not gate_keys:
        return path_board
    if _downtown_gate_open(gate_keys, downtown_boards):
        return path_board
    labels = [
        (downtown_boards.get(key) or {}).get("label", key)
        for key in gate_keys
    ]
    out = dict(path_board or {"label": path_station, "trains": []})
    out["label"] = path_station
    out["trains"] = []
    if len(labels) == 1:
        out["note"] = "no %s southbound" % labels[0]
    else:
        out["note"] = "no %s southbound" % " / ".join(labels)
    out["error"] = None
    return out


def _path_mt_jc_board(station_label, path_bundle, fetch_json, now=None):
    from lib.path_trains import _is_mt_to_jc_path_destination

    return get_path_station_board(
        station_label,
        "nj",
        dest_filter=_is_mt_to_jc_path_destination,
        fetch_json=fetch_json,
        panynj_payload=path_bundle.get("_payload"),
        max_trains=MT_TO_JC_MAX_TRAINS,
        raw_pool=MT_PATH_RAW_POOL,
        allow_hoboken=True,
        now=now,
    )


def _path_transit_mt_jc(station_label):
    from lib.path_trains import _is_mt_to_jc_path_destination

    def _fetch():
        return get_path_transit_board(
            station_label,
            "nj",
            dest_filter=_is_mt_to_jc_path_destination,
            max_trains=MT_TO_JC_MAX_TRAINS,
            raw_pool=TRANSIT_TRANSFER_RAW_POOL,
        )

    return _fetch


def _hblr_south_board(station, now=None):
    return get_hblr_board(
        station,
        "to_liberty_state_park",
        now=now,
        max_trains=MT_TO_JC_MAX_TRAINS,
        raw_pool=MT_HBLR_RAW_POOL,
    )


def _hblr_transit_south(station):
    def _fetch():
        return get_hblr_transit_board(
            station,
            "to_liberty_state_park",
            max_trains=MT_TO_JC_MAX_TRAINS,
            raw_pool=TRANSIT_TRANSFER_RAW_POOL,
        )

    return _fetch


def _chain_path_from_subway(subway, path_raw, offset, subway_short, path_short):
    """PATH Nwk/JSQ/Hoboken catchable after subway; PANYNJ then Transit retry."""
    if not _subway_available(subway):
        return _gate_on_subway(subway, path_raw, path_short)
    return resolve_transfer_board(
        subway,
        path_raw,
        offset,
        subway_short,
        path_short,
        transit_secondary_fetcher=_path_transit_mt_jc(path_short),
        fallback_current=False,
        fallback_suffix="PATH",
    )


def _chain_hblr_from_path(subway, path_board, hblr_raw, offset, path_short, hblr_short):
    """HBLR southbound catchable after PATH; gated when subway or PATH unavailable."""
    if not _subway_available(subway):
        return _gate_on_subway(subway, hblr_raw, hblr_short)
    if not _earliest_minutes(path_board):
        out = dict(hblr_raw or {"label": hblr_short, "trains": []})
        out["trains"] = []
        out["note"] = "no %s yet" % path_short
        out["error"] = None
        return out
    return resolve_transfer_board(
        path_board,
        hblr_raw,
        offset,
        path_short,
        hblr_short,
        transit_secondary_fetcher=_hblr_transit_south(hblr_short.replace(" HBLR", "")),
        fallback_current=False,
        fallback_suffix="HBLR",
    )


def build_mt_to_jc_rows(path_bundle, fetch_json=None, now=None):
    """Uptown subway rows; downtown gates clear PATH when southbound unavailable."""
    now = now or datetime.now()
    subway_cache = {}
    downtown_boards = _load_downtown_gates(fetch_json, now=now)
    rows = []

    for cfg in MT_TO_JC_ROWS:
        row_id = cfg["id"]
        subway_key = cfg["subway_key"]
        if subway_key not in subway_cache:
            subway_cache[subway_key] = _load_mt_subway_board(
                subway_key, fetch_json, now=now
            )
        subway = subway_cache[subway_key]
        subway_short = subway["label"]
        include_wtc = cfg.get("include_wtc_path", True)

        path_primary_label = cfg["path_primary"]["station"]
        path_primary_raw = _path_mt_jc_board(
            path_primary_label, path_bundle, fetch_json, now=now
        )
        path_primary = _chain_path_from_subway(
            subway,
            path_primary_raw,
            cfg["path_primary"]["offset"],
            subway_short,
            path_primary_label,
        )
        path_primary = _gate_path_on_downtown(
            path_primary, path_primary_label, row_id, downtown_boards
        )

        path_wtc = None
        hblr_exchange = None
        if include_wtc:
            path_wtc_raw = _path_mt_jc_board("WTC", path_bundle, fetch_json, now=now)
            path_wtc = _chain_path_from_subway(
                subway,
                path_wtc_raw,
                cfg["path_wtc_offset"],
                subway_short,
                "WTC",
            )
            path_wtc = _gate_path_on_downtown(path_wtc, "WTC", row_id, downtown_boards)

        hblr_newport_raw = _hblr_south_board("Newport", now=now)
        hblr_newport = _chain_hblr_from_path(
            subway,
            path_primary,
            hblr_newport_raw,
            cfg["hblr_newport_offset"],
            path_primary_label,
            "Newport HBLR",
        )

        if include_wtc:
            hblr_exchange_raw = _hblr_south_board("Exchange Place", now=now)
            hblr_exchange = _chain_hblr_from_path(
                subway,
                path_wtc,
                hblr_exchange_raw,
                cfg["hblr_exchange_offset"],
                "WTC",
                "Exchange HBLR",
            )

        rows.append(
            {
                "id": row_id,
                "label": subway_short,
                "subway": subway,
                "path_primary": path_primary,
                "path_wtc": path_wtc,
                "hblr_newport": hblr_newport,
                "hblr_exchange": hblr_exchange,
            }
        )
    return rows
