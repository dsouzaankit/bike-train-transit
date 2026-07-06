# -*- coding: utf-8 -*-
"""MT → JC tab — subway → PATH (Nwk/JSQ/Hoboken) → HBLR southbound connection rows."""

from __future__ import annotations

from datetime import datetime

from lib.hblr_path import (
    HBLR_PATH_MAX_TRAINS,
    TRANSIT_TRANSFER_RAW_POOL,
    apply_transfer_filter,
    resolve_transfer_board,
)
from lib.light_rail import get_hblr_board, get_hblr_transit_board
from lib.path_trains import get_path_station_board, get_path_transit_board
from lib.subway_lines import normalize_line
from lib.subway_trains import (
    SUBWAY_DIRECTION_SOUTH,
    SUBWAY_FETCH_LIMIT,
    _trains_per_line,
    fetch_station_arrivals,
)

MT_TO_JC_MAX_TRAINS = HBLR_PATH_MAX_TRAINS
MT_PATH_RAW_POOL = max(12, TRANSIT_TRANSFER_RAW_POOL)
MT_HBLR_RAW_POOL = 36

# GTFS stop IDs for subwayinfo.nyc (125 / F11 are best-guess — verify on device).
MT_SUBWAY_SOURCES = {
    "50_8av": {
        "label": "50 St (8Av)",
        "stations": ({"station_id": "A25", "direction": SUBWAY_DIRECTION_SOUTH},),
        "line_specs": (
            ("E", SUBWAY_DIRECTION_SOUTH),
            ("F", SUBWAY_DIRECTION_SOUTH),
        ),
    },
    "50_7av": {
        "label": "50 St (7Av)",
        "stations": ({"station_id": "125", "direction": SUBWAY_DIRECTION_SOUTH},),
        "line_specs": (
            ("1", SUBWAY_DIRECTION_SOUTH),
            ("F", SUBWAY_DIRECTION_SOUTH),
        ),
    },
    "lex_53": {
        "label": "Lex/53 St",
        "stations": ({"station_id": "F11", "direction": SUBWAY_DIRECTION_SOUTH},),
        "line_specs": (
            ("E", SUBWAY_DIRECTION_SOUTH),
            ("1", SUBWAY_DIRECTION_SOUTH),
            ("F", SUBWAY_DIRECTION_SOUTH),
        ),
    },
}

MT_SUBWAY_LINE_SPECS = (
    ("E", SUBWAY_DIRECTION_SOUTH),
    ("1", SUBWAY_DIRECTION_SOUTH),
    ("F", SUBWAY_DIRECTION_SOUTH),
)

MT_TO_JC_ROWS = (
    {
        "id": "mt_50_8av",
        "subway_key": "50_8av",
        "path_primary": {"station": "9 St", "offset": 15},
        "path_wtc_offset": 19,
        "hblr_newport_offset": 14,
        "hblr_exchange_offset": 7,
    },
    {
        "id": "mt_50_7av",
        "subway_key": "50_7av",
        "path_primary": {"station": "Chris St", "offset": 15},
        "path_wtc_offset": 20,
        "hblr_newport_offset": 13,
        "hblr_exchange_offset": 7,
    },
    {
        "id": "mt_lex_53",
        "subway_key": "lex_53",
        "path_primary": {"station": "9 St", "offset": 20},
        "path_wtc_offset": 25,
        "hblr_newport_offset": 14,
        "hblr_exchange_offset": 7,
    },
)


def f_line_active(now=None):
    """F line shown on MT→JC subway cards: Mon–Fri 6:00 AM – 9:30 PM."""
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    clock = now.hour * 60 + now.minute
    return 6 * 60 <= clock < 21 * 60 + 30


def _load_mt_subway_board(source_key, fetch_json, now=None):
    now = now or datetime.now()
    source = MT_SUBWAY_SOURCES[source_key]
    label = source["label"]
    line_specs = source.get("line_specs") or MT_SUBWAY_LINE_SPECS
    merged = []
    error = None
    for station in source["stations"]:
        try:
            merged.extend(
                fetch_station_arrivals(
                    station,
                    fetch_json,
                    limit=SUBWAY_FETCH_LIMIT,
                )
            )
        except Exception as exc:
            error = str(exc)

    if not f_line_active(now):
        merged = [
            train
            for train in merged
            if normalize_line(train.get("line")) != "F"
        ]

    trains = _trains_per_line(merged, line_specs=line_specs, per_line=1)
    note = None
    if not f_line_active(now):
        note = "F wkdys 6a–9:30p"
    return {
        "label": label,
        "trains": trains,
        "by_line": True,
        "error": error if not trains else None,
        "note": note,
        "_raw_trains": merged,
        "_line_specs": line_specs,
        "_per_line": 1,
        "source": "subwayapi" if merged else None,
    }


def _path_mt_jc_board(station_label, path_bundle, fetch_json):
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


def _chain_hblr_from_path(path_board, hblr_raw, offset, path_short, hblr_short):
    """HBLR southbound catchable after PATH; Transit retry, no current-platform fallback."""
    station = hblr_short.replace(" HBLR", "")
    return resolve_transfer_board(
        path_board,
        hblr_raw,
        offset,
        path_short,
        hblr_short,
        transit_secondary_fetcher=_hblr_transit_south(station),
        fallback_current=False,
        fallback_suffix="HBLR",
    )


def build_mt_to_jc_rows(path_bundle, fetch_json=None, now=None):
    """Three MT→JC rows with subway → PATH → HBLR chained offsets."""
    now = now or datetime.now()
    subway_cache = {}
    rows = []

    for cfg in MT_TO_JC_ROWS:
        subway_key = cfg["subway_key"]
        if subway_key not in subway_cache:
            subway_cache[subway_key] = _load_mt_subway_board(
                subway_key, fetch_json, now=now
            )
        subway = subway_cache[subway_key]
        subway_short = subway["label"]

        path_primary_label = cfg["path_primary"]["station"]
        path_primary_raw = _path_mt_jc_board(
            path_primary_label, path_bundle, fetch_json
        )
        path_wtc_raw = _path_mt_jc_board("WTC", path_bundle, fetch_json)

        path_primary = _chain_path_from_subway(
            subway,
            path_primary_raw,
            cfg["path_primary"]["offset"],
            subway_short,
            path_primary_label,
        )
        path_wtc = _chain_path_from_subway(
            subway,
            path_wtc_raw,
            cfg["path_wtc_offset"],
            subway_short,
            "WTC",
        )

        hblr_newport_raw = _hblr_south_board("Newport", now=now)
        hblr_exchange_raw = _hblr_south_board("Exchange Place", now=now)

        hblr_newport = _chain_hblr_from_path(
            path_primary,
            hblr_newport_raw,
            cfg["hblr_newport_offset"],
            path_primary_label,
            "Newport HBLR",
        )
        hblr_exchange = _chain_hblr_from_path(
            path_wtc,
            hblr_exchange_raw,
            cfg["hblr_exchange_offset"],
            "WTC",
            "Exchange HBLR",
        )

        rows.append(
            {
                "id": cfg["id"],
                "label": subway_short,
                "subway": subway,
                "path_primary": path_primary,
                "path_wtc": path_wtc,
                "hblr_newport": hblr_newport,
                "hblr_exchange": hblr_exchange,
            }
        )
    return rows
