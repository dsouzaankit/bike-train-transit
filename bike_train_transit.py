# -*- coding: utf-8 -*-
"""
Bike / train / transit viewer for Pythonista (iPhone).

Setup:
1. Copy the bike_train_transit folder into Pythonista (script + lib/)
2. Run bike_train_transit.py once in Pythonista (installs launcher)
3. Use Shortcuts URL from console/log, or:
   pythonista3://RunBikeTrainTransit.py?action=run

LAN debug (from PC on same Wi-Fi):
   http://<phone-ip>:8765/
   python debug_server.py --safe   # logs only after a crash

Debug entrypoints (disable one data source; full UI otherwise):
   python debug_citibike_inactive.py
   python debug_path_inactive.py
   python debug_subway_inactive.py
   python debug_hblr_inactive.py
   # or: BIKE_TRAIN_TRANSIT_INACTIVE=subway,path python bike_train_transit.py --cli
"""

import argparse
import json
import os
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

try:
    import ui

    HAS_UI = True
except ImportError:
    HAS_UI = False

# --- edit these ---
APP_TITLE = "JC <-> NYC Transit"
REGION = "JC"
STATIONS = [
    "Dixon Mills",
    "Montgomery St",
    "Brunswick & 6th",
    "Monmouth & 6th",
    "Jersey & 6th St",
    "Newport PATH",
    "Washington St",
    "City Hall",
    "Grove St PATH",
    "Liberty Light Rail",
    "Exchange Pl",
    "JC Medical Center",
]
# Shorter labels for compact UI (same order as STATIONS). Use \n for a two-line name.
STATION_LABELS = [
    "Dixon Mills",
    "Montgomery",
    "Brunswick",
    "Monmouth",
    "Jersey & 6th",
    "Newport PATH",
    "Washington St",
    "City Hall",
    "Grove St PATH",
    "Liberty\nLight Rail",
    "Exchange Pl",
    "JC\nMedical Center",
]
# Snapshot indices (matches STATIONS order above):
#   0 Dixon Mills  1 Montgomery  |  2 Brunswick  3 Monmouth  4 Jersey & 6th
#   5 Newport PATH  6 Washington  |  7 City Hall  8 Grove St PATH
#   9 Liberty Light Rail  10 Exchange Pl  |  11 JC Medical Center (own row)
#
# Group 1 — 6th St (2x2, empty cell beside Jersey)
# Group 2 — Newport PATH, Washington St
# Group 3 — Dixon Mills, Montgomery St
GRID_GROUPS = [
    [(0, 1)],              # Group 3
    [(2, 3), (4, None)],   # Group 1
    [(5, 6)],              # Group 2
    [(7, 8)],              # City Hall, Grove St PATH
    [(9, 10)],             # Liberty Light Rail, Exchange Pl
    [(11, None)],          # JC Medical Center
]


def _build_grid_slots():
    slots = []
    for row_pair in GRID_GROUPS:
        for left, right in row_pair:
            slots.append(left)
            slots.append(right)
    return slots


GRID_SLOTS = _build_grid_slots()
ALERT_MIN_BIKES = 2
ALERT_MIN_DOCKS = 2
# --- end edit ---

CARD_HEIGHT = 76
CARD_GAP = 6
CARD_COLUMNS = 2
PATH_CARD_HEIGHT = 98
TRANSIT_LINE_ROW_HEIGHT = 22
TUNNEL_ROW_HEIGHT = 40
ETA_COLUMN_WIDTH = 68
HBLR_PATH_ETA_WIDTH = 52
SECTION_HEADER_HEIGHT = 26
SECTION_GAP = 10
TAB_BAR_HEIGHT = 34
TOP_CONTENT_INSET = 43  # fallback when safe_area_insets unavailable
# Thumb float tuned for ~6" portrait (412×892 class); scales with safe area.
PHONE6_REF_W = 412
PHONE6_REF_USABLE_H = 811  # 892 − ~47 top − ~34 home indicator
THUMB_FLOAT_SEC = 5.0
THUMB_FLOAT_MARGIN_EDGE = 16
THUMB_FLOAT_MARGIN_BOTTOM = 20  # stack anchor above home indicator
THUMB_FLOAT_BTN_GAP = 14
THUMB_FLOAT_STACK_X_RATIO = 0.50  # column on vertical screen center line
THUMB_FLOAT_STACK_Y_RATIO = 0.65  # stack center — lower half for thumb reach
THUMB_FLOAT_BTN_H_BASE = 50
THUMB_PROLONG_W_BASE = 108
THUMB_FLOAT_TAB_W_BASE = 100
THUMB_FLOAT_SCALE_MAX = 1.12
THUMB_FLOAT_TAP_HIGHLIGHT = "#1a5fd4"  # instant tap ack (brighter than accent)
TAB_BUSY_BG = "#252b33"  # tab pills while refresh in progress

LAN_DEBUG_ENABLED = True
LAN_DEBUG_PORT = 8765
LISTEN_HOST = "0.0.0.0"
SHORTCUT_URL = "pythonista3://bike_train_transit/bike_train_transit.py?action=run"

GBFS_BASE = "https://gbfs.citibikenyc.com/gbfs/en"
_debug_started = False
TRANSIT_FETCH_TIMEOUT = 12
BUILD_TAG = "hblr-path-v71"


def _cache_ttl_suffix() -> str:
    from lib.http_cache import min_remaining_ttl_sec

    sec = min_remaining_ttl_sec()
    if sec is None:
        return ""
    return " · cache %ds" % sec

COLORS = {
    "bg": "#0f1419",
    "card": "#1c2430",
    "card_alert": "#3a2222",
    "text": "#ffffff",
    "muted": "#8b98a5",
    "accent": "#003da5",
    "filled": "#34c759",
    "empty": "#5ac8fa",
    "warn": "#ff9f0a",
    "bad": "#ff453a",
}


def log_event(message):
    try:
        from lib.file_logging import log_message

        log_message(message)
    except Exception:
        pass


def print_shortcut_help():
    # Always print from main module — works even if lib/ on phone is stale.
    print("", flush=True)
    print("=== iOS Shortcut URL (run as main script) ===", flush=True)
    print(SHORTCUT_URL, flush=True)
    print("Home Screen: Shortcuts -> URL action + Open URLs action (two actions)", flush=True)
    try:
        from lib.shortcut_launcher import LAUNCHER_VERSION, launcher_help_lines
        from lib.local_deploy import local_app_dir

        lines = launcher_help_lines(_SCRIPT_DIR, install=True)
        print("(lib/shortcut_launcher.py v%s)" % LAUNCHER_VERSION, flush=True)
        print("Shortcut runs from: %s" % local_app_dir(), flush=True)
    except Exception as exc:
        print("lib/ shortcut help unavailable: %s" % exc, flush=True)
        print("Re-sync the whole bike_train_transit folder (include lib/).", flush=True)
        lines = [
            "1. Shortcuts -> + -> Open URLs",
            "2. URL: %s" % SHORTCUT_URL,
            "3. Add to Home Screen",
        ]
    text = "\n".join(lines)
    print(text, flush=True)
    try:
        from lib.file_logging import log_banner

        log_banner(text.strip())
    except Exception:
        pass


def setup_debug(mode="full"):
    from lib.file_logging import log_banner, setup_file_logging
    from lib.log_paths import write_ok_probe

    if mode == "safe":
        return
    setup_file_logging()
    write_ok_probe(mode=mode)
    from lib.debug_flags import inactive_summary

    inactive = inactive_summary()
    extra = " inactive={}".format(inactive) if inactive else ""
    log_banner(
        "Bike Train Transit app started mode={} stations={} build={}{}".format(
            mode, len(STATIONS), BUILD_TAG, extra
        )
    )


def _lan_debug_url(path="/"):
    from lib.net_util import format_lan_debug_url

    return format_lan_debug_url(LAN_DEBUG_PORT, path, listen_host=LISTEN_HOST)


def debug_status():
    from lib import app_state
    from lib.debug_flags import inactive_summary
    from lib.http_cache import (
        HTTP_CACHE_TTL_SEC,
        disk_entry_count,
        min_remaining_ttl_sec,
        stats_snapshot,
    )

    status = app_state.snapshot()
    inactive = inactive_summary()
    if inactive:
        status["inactive"] = inactive
    status["httpCache"] = stats_snapshot()
    status["httpCache"]["diskEntries"] = disk_entry_count()
    status["httpCache"]["ttlSec"] = HTTP_CACHE_TTL_SEC
    remaining = min_remaining_ttl_sec()
    if remaining is not None:
        status["httpCache"]["minRemainingSec"] = remaining
    return status


def start_debug_server(safe_mode=False):
    global _debug_started
    if not LAN_DEBUG_ENABLED or _debug_started:
        return
    from lib.lan_debug_server import start_lan_debug_server_thread

    start_lan_debug_server_thread(
        LISTEN_HOST,
        LAN_DEBUG_PORT,
        safe_mode=safe_mode,
        status_fn=debug_status,
    )
    _debug_started = True
    banner = "LAN debug: " + _lan_debug_url()
    print(banner, flush=True)
    log_event(banner)


def _decode_response(raw):
    """Decode an HTTP body to str across Pythonista's quirky buffer types.

    Some Pythonista builds return a buffer object whose decode() rejects the
    ``errors`` keyword, so normalize to real bytes before decoding.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, tuple):
        raw = raw[0] if raw else b""
        if isinstance(raw, str):
            return raw
    try:
        return raw.decode("utf-8", "replace")
    except (TypeError, AttributeError):
        return bytes(raw).decode("utf-8", "replace")


def _short_fetch_url(url):
    from lib.http_cache import normalize_cache_url

    text = normalize_cache_url(url)
    if len(text) <= 72:
        return text
    return text[:69] + "..."


def _gbfs_cache_kind(url: str) -> tuple[str, bool] | None:
    """Return (label, require_name) for Citibike GBFS feeds we validate in cache."""
    from lib.http_cache import normalize_cache_url

    path = urllib.parse.urlparse(normalize_cache_url(url)).path
    if path.endswith("/station_information.json"):
        return ("station_information", True)
    if path.endswith("/station_status.json"):
        return ("station_status", False)
    return None


def _validate_gbfs_payload(url: str, payload: dict) -> None:
    kind = _gbfs_cache_kind(url)
    if not kind:
        return
    label, require_name = kind
    stations = _gbfs_stations(payload, label, require_name=require_name)
    if not stations:
        raise ValueError("%s response has no stations" % label)


def fetch_json(url, timeout=30, retries=2):
    from lib.http_cache import (
        get_cached_json,
        invalidate_cached_json,
        store_cached_json,
        _record_miss,
    )

    cached = get_cached_json(url)
    if cached is not None:
        if not isinstance(cached, dict):
            invalidate_cached_json(url)
            log_event(
                "http cache reject %s: expected object, got %s"
                % (_short_fetch_url(url), type(cached).__name__)
            )
        else:
            try:
                _validate_gbfs_payload(url, cached)
                log_event("http cache hit: %s" % _short_fetch_url(url))
                return cached
            except ValueError as exc:
                invalidate_cached_json(url)
                log_event(
                    "http cache reject %s: %s" % (_short_fetch_url(url), exc)
                )

    _record_miss()
    last_error = None
    for attempt in range(max(1, retries + 1)):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "bike-train-transit/2.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            text = _decode_response(raw)
            payload = json.loads(text)
            if isinstance(payload, tuple):
                raise ValueError(
                    "JSON decoder returned tuple from %s (attempt %s)"
                    % (url, attempt + 1)
                )
            if not isinstance(payload, dict):
                raise ValueError(
                    "Expected JSON object from %s, got %s"
                    % (url, type(payload).__name__)
                )
            _validate_gbfs_payload(url, payload)
            store_cached_json(url, payload)
            return payload
        except Exception as exc:
            last_error = exc
            log_event("fetch_json retry {} for {}: {}".format(attempt + 1, url, exc))
    raise last_error


def _gbfs_stations(payload, label="GBFS", require_name=False):
    if not isinstance(payload, dict):
        raise ValueError("%s response is not an object: %s" % (label, type(payload).__name__))
    data = payload.get("data")
    stations = None
    if isinstance(data, dict):
        stations = data.get("stations")
    elif isinstance(data, list):
        stations = data
    if not isinstance(stations, list):
        raise ValueError("%s response missing stations list" % label)
    for index, station in enumerate(stations):
        if not isinstance(station, dict):
            raise ValueError(
                "%s station[%s] is %s, expected object"
                % (label, index, type(station).__name__)
            )
        if "station_id" not in station:
            raise ValueError("%s station[%s] missing station_id" % (label, index))
        if require_name and "name" not in station:
            raise ValueError("%s station[%s] missing name" % (label, index))
    return stations


def station_lookup():
    info = fetch_json(GBFS_BASE + "/station_information.json")
    by_id = {}
    by_name = {}
    for s in _gbfs_stations(info, "station_information", require_name=True):
        sid = str(s["station_id"])
        name = s["name"]
        by_id[sid] = name
        by_name[name.casefold()] = sid
        if "legacy_id" in s:
            by_id[str(s["legacy_id"])] = name
    return by_id, by_name


def fetch_transit_json(url):
    return fetch_json(url, timeout=TRANSIT_FETCH_TIMEOUT)


def fetch_transit_payload(url):
    """Like fetch_transit_json but accepts JSON arrays (e.g. PANYNJ crossing times)."""
    from lib.http_cache import get_cached_json, store_cached_json, _record_miss

    cached = get_cached_json(url)
    if cached is not None:
        if isinstance(cached, (dict, list)):
            log_event("http cache hit: %s" % _short_fetch_url(url))
            return cached
        raise ValueError(
            "Cached JSON for %s is %s, expected object or array"
            % (url, type(cached).__name__)
        )

    _record_miss()
    last_error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "bike-train-transit/2.0"}
            )
            with urllib.request.urlopen(req, timeout=TRANSIT_FETCH_TIMEOUT) as resp:
                raw = resp.read()
            text = _decode_response(raw)
            payload = json.loads(text)
            if isinstance(payload, (dict, list)):
                store_cached_json(url, payload)
                return payload
            raise ValueError("Expected JSON object or array from %s" % url)
        except Exception as exc:
            last_error = exc
    raise last_error


def _placeholder_snapshot(label="No data"):
    return {
        "region": REGION,
        "name": label,
        "label": label,
        "bikes": 0,
        "docks": 0,
        "capacity": 0,
        "fill": None,
        "renting": False,
        "returning": False,
        "low_bikes": False,
        "low_docks": False,
    }


def resolve_id(raw, by_id, by_name):
    if raw in by_id:
        return raw
    exact = by_name.get(raw.casefold())
    if exact:
        return exact
    matches = [sid for sid, name in by_id.items() if raw.casefold() in name.casefold()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = sorted({by_id[m] for m in matches})
        raise ValueError("Ambiguous station %r. Matches: %s" % (raw, ", ".join(names)))
    raise ValueError("Unknown station: %r" % raw)


def get_snapshots():
    from lib.debug_flags import is_active

    if not is_active("citibike"):
        log_event("debug: citibike inactive — placeholder dock cards")
        out = []
        for index, raw in enumerate(STATIONS):
            label = STATION_LABELS[index] if index < len(STATION_LABELS) else raw
            snap = _placeholder_snapshot(label)
            snap["name"] = raw
            out.append(snap)
        return out

    by_id, by_name = station_lookup()
    status = fetch_json(GBFS_BASE + "/station_status.json")
    status_by_id = {
        str(s["station_id"]): s for s in _gbfs_stations(status, "station_status")
    }

    out = []
    for index, raw in enumerate(STATIONS):
        sid = resolve_id(raw, by_id, by_name)
        st = status_by_id.get(sid)
        if not st:
            raise ValueError("No status for %s" % raw)
        bikes = int(st.get("num_bikes_available", 0))
        docks = int(st.get("num_docks_available", 0))
        cap = bikes + docks
        fill = None if cap == 0 else round(100.0 * bikes / cap, 1)
        label = STATION_LABELS[index] if index < len(STATION_LABELS) else raw
        out.append(
            {
                "region": REGION,
                "name": by_id.get(sid, raw),
                "label": label,
                "bikes": bikes,
                "docks": docks,
                "capacity": cap,
                "fill": fill,
                "renting": bool(st.get("is_renting", 0)),
                "returning": bool(st.get("is_returning", 0)),
                "low_bikes": ALERT_MIN_BIKES and bikes <= ALERT_MIN_BIKES,
                "low_docks": ALERT_MIN_DOCKS and docks <= ALERT_MIN_DOCKS,
            }
        )
    return out


def tagged_name(snapshot):
    return "[%s] %s" % (snapshot["region"], snapshot.get("label", snapshot["name"]))


def get_path_boards():
    from lib.path_trains import get_path_nyc_boards

    return get_path_nyc_boards(fetch_transit_json)


def get_path_33rd_boards():
    from lib.path_trains import get_path_33rd_boards as _get_path_33rd_boards

    return _get_path_33rd_boards(fetch_transit_json)


def get_subway_boards():
    from lib.subway_trains import get_subway_north_boards

    return get_subway_north_boards(fetch_transit_json)


def get_subway_to_jc_boards():
    from lib.subway_trains import get_subway_to_jc_boards as _get_subway_to_jc_boards

    return _get_subway_to_jc_boards(fetch_transit_json)


def get_path_nj_boards():
    from lib.path_trains import get_path_nj_boards as _get_path_nj_boards

    return _get_path_nj_boards(fetch_transit_json)


def get_hblr_path_sections(path_bundle):
    from lib.debug_flags import is_active
    from lib.hblr_path import build_hblr_path_sections

    if not is_active("hblr"):
        log_event("debug: hblr inactive — skip HBLR↔PATH sections")
        return []
    return build_hblr_path_sections(path_bundle, fetch_json=fetch_transit_json)


def _transit_fetch_jobs():
    """Ordered transit fetch jobs (one TLS burst each)."""
    from lib.debug_flags import is_active

    jobs = [
        (
            "tunnels",
            lambda: __import__(
                "lib.tunnel_crossings", fromlist=["get_tunnel_boards"]
            ).get_tunnel_boards(fetch_transit_payload),
        ),
    ]
    if is_active("path"):

        def _fetch_path_all():
            from lib.path_trains import get_all_path_boards

            return get_all_path_boards(fetch_transit_json)

        jobs.append(("pathAll", _fetch_path_all))
    else:
        log_event("debug: path inactive — skip PATH fetch")
    if is_active("subway"):
        jobs.append(("subway", get_subway_boards))
        jobs.append(("subwayToJc", get_subway_to_jc_boards))
    else:
        log_event("debug: subway inactive — skip subway fetch")
    return jobs


def _assemble_transit_boards(results):
    """Merge staged transit job results into render payload fields."""
    from lib.debug_flags import is_active

    path_bundle = results.get("pathAll") or {}
    path_boards = path_bundle.get("nyc") or []
    path_33rd_boards = path_bundle.get("33rd") or []
    path_nj_boards = path_bundle.get("nj") or []
    subway_boards = results.get("subway") or []
    subway_to_jc_boards = results.get("subwayToJc") or []
    tunnel_boards = results.get("tunnels") or []
    if is_active("subway") and is_active("path"):
        try:
            log_event(
                "step: transit connections (subway={} path33={})".format(
                    len(subway_boards or []), len(path_33rd_boards or [])
                )
            )
            from lib.subway_trains import apply_path_subway_connections

            subway_boards = apply_path_subway_connections(subway_boards, path_33rd_boards)
            log_event("step: transit connections done ({})".format(len(subway_boards or [])))
        except Exception as exc:
            log_event("PATH+subway connection failed: {}".format(exc))
            log_event(traceback.format_exc())
    path_exchange_wtc = None
    subway_wtc_north = []
    try:
        hblr_path_sections = get_hblr_path_sections(path_bundle)
    except Exception as exc:
        log_event("HBLR path sections failed: {}".format(exc))
        log_event(traceback.format_exc())
        hblr_path_sections = []
    lsp_primary = None
    if hblr_path_sections:
        lsp_primary = (hblr_path_sections[0] or {}).get("primary")
    if is_active("path") and is_active("subway"):
        try:
            from lib.hblr_path import HBLR_PATH_MAX_TRAINS
            from lib.path_trains import get_exchange_place_wtc_board
            from lib.subway_trains import (
                apply_exchange_wtc_subway_connections,
                get_wtc_north_boards,
            )

            path_exchange_wtc = get_exchange_place_wtc_board(
                fetch_transit_json,
                panynj_payload=path_bundle.get("_payload"),
                max_trains=HBLR_PATH_MAX_TRAINS,
            )
            subway_wtc_north = apply_exchange_wtc_subway_connections(
                path_exchange_wtc,
                get_wtc_north_boards(fetch_transit_json),
                lsp_primary=lsp_primary,
            )
        except Exception as exc:
            log_event("PATH+subway WTC connection failed: {}".format(exc))
            log_event(traceback.format_exc())
    elif not is_active("path"):
        log_event("debug: path inactive — skip Exchange WTC PATH")
    elif not is_active("subway"):
        log_event("debug: subway inactive — skip WTC subway chain")
    log_event("step: HBLR↔PATH sections ({})".format(len(hblr_path_sections or [])))
    log_event("step: transit boards assembled")
    return (
        path_boards,
        path_33rd_boards,
        subway_boards,
        path_nj_boards,
        subway_to_jc_boards,
        tunnel_boards,
        hblr_path_sections,
        path_exchange_wtc,
        subway_wtc_north,
    )


def _fetch_transit_boards():
    """Fetch all transit boards sequentially; never raise."""
    jobs = _transit_fetch_jobs()
    log_event("step: transit jobs ({})".format(",".join(key for key, _ in jobs)))
    results = {}
    for key, fn in jobs:
        log_event("step: transit {} start".format(key))
        try:
            results[key] = fn()
            log_event("step: transit {} ok".format(key))
        except Exception as exc:
            log_event("{} fetch failed: {}".format(key, exc))
            log_event(traceback.format_exc())
            results[key] = [] if key != "pathAll" else {}
    return _assemble_transit_boards(results)


def print_subway_boards(boards, title="Subway"):
    from lib.subway_trains import print_subway_boards as _print_subway_boards

    _print_subway_boards(boards, title=title)


def print_path_boards(boards, title="PATH to NYC"):
    from lib.path_trains import print_path_boards as _print_path_boards

    _print_path_boards(boards, title=title)


def print_snapshots(snapshots):
    print("Bike dock status [%s]" % REGION)
    print("Checked at: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("")
    for snapshot in snapshots:
        alert = snapshot["low_bikes"] or snapshot["low_docks"]
        marker = " [!]" if alert else ""
        fill = "n/a" if snapshot["fill"] is None else "%s%%" % snapshot["fill"]
        print("%s%s" % (tagged_name(snapshot), marker))
        print("  FILLED: %s   EMPTY: %s" % (snapshot["bikes"], snapshot["docks"]))
        print("  %s full  |  capacity %s" % (fill, snapshot["capacity"]))
        if snapshot["low_bikes"]:
            print("  ** low bikes")
        if snapshot["low_docks"]:
            print("  ** low docks")
        print("")


def main_cli():
    setup_debug(mode="cli")
    start_debug_server(safe_mode=False)
    try:
        snapshots = get_snapshots()
        (
            path_boards,
            path_33rd_boards,
            subway_boards,
            path_nj_boards,
            subway_to_jc_boards,
            tunnel_boards,
            hblr_path_sections,
            path_exchange_wtc,
            subway_wtc_north,
        ) = _fetch_transit_boards()
        print_snapshots(snapshots)
        print("")
        print_path_boards(path_boards)
        print("")
        print_path_boards(path_33rd_boards, title="PATH to 33rd St")
        print("")
        print_path_boards(path_nj_boards, title="PATH to NJ")
        print("")
        print_subway_boards(subway_boards, title="Subway North / Queens")
        print("")
        if path_exchange_wtc or subway_wtc_north:
            print_path_boards(
                [path_exchange_wtc] if path_exchange_wtc else [],
                title="PATH Exchange Place → WTC",
            )
            print("")
            print_subway_boards(subway_wtc_north, title="Subway WTC north (after Exchange PATH +8)")
            print("")
        print_subway_boards(subway_to_jc_boards, title="Subway To JC")
        print("")
        for section in hblr_path_sections or []:
            print(section.get("title"))
            if section.get("layout") == "shared_primary":
                boards = [section.get("primary")] + [
                    conn.get("board") for conn in section.get("connections") or []
                ]
            else:
                boards = [section.get("primary"), section.get("secondary")]
            for board in boards:
                board = board or {}
                trains = ", ".join(
                    "%s %s" % (t.get("eta"), t.get("destination")) for t in board.get("trains") or []
                ) or (board.get("error") or board.get("note") or "(none)")
                print("  %s: %s" % (board.get("label"), trains))
        from lib.tunnel_crossings import print_tunnel_boards

        print_tunnel_boards(tunnel_boards)
        from lib import app_state

        app_state.update_cli(
            snapshots,
            path_boards,
            subway_boards,
            path_33rd_boards,
            path_nj_boards,
            subway_to_jc_boards,
            tunnel_boards=tunnel_boards,
            tagged_name_fn=tagged_name,
        )
        log_event("CLI refresh OK: {} stations".format(len(snapshots)))
    except Exception as exc:
        from lib import app_state

        app_state.set_error(str(exc))
        log_event("CLI refresh failed: {}".format(exc))
        log_event(traceback.format_exc())
        raise


if HAS_UI:

    def make_label(text, font_size=16, bold=False, color=COLORS["text"], align=ui.ALIGN_LEFT, wrap=True):
        label = ui.Label()
        label.text = text
        label.font = ("<system-bold>" if bold else "<system>", font_size)
        label.text_color = color
        label.alignment = align
        label.number_of_lines = 0 if wrap else 1
        return label

    class StationCard(ui.View):
        def __init__(self, snapshot, card_width):
            super().__init__()
            alert = snapshot["low_bikes"] or snapshot["low_docks"]
            self.background_color = COLORS["card_alert"] if alert else COLORS["card"]
            self.corner_radius = 10
            self.border_width = 1
            self.border_color = COLORS["bad"] if alert else "#2a3441"
            self.height = CARD_HEIGHT

            tag = make_label(REGION, font_size=10, bold=True, color=COLORS["accent"])
            tag.frame = (8, 6, 28, 14)

            label_text = snapshot["label"]
            if "\n" in label_text:
                name = make_label(label_text, font_size=11, bold=True)
                name.frame = (38, 2, card_width - 46, 28)
            else:
                name = make_label(label_text, font_size=13, bold=True)
                name.frame = (38, 4, card_width - 46, 18)

            filled = make_label(str(snapshot["bikes"]), font_size=28, bold=True)
            filled.text_color = COLORS["bad"] if snapshot["low_bikes"] else COLORS["filled"]
            filled.alignment = ui.ALIGN_CENTER
            filled.frame = (8, 26, (card_width - 16) // 2, 34)

            empty = make_label(str(snapshot["docks"]), font_size=28, bold=True)
            empty.text_color = COLORS["bad"] if snapshot["low_docks"] else COLORS["empty"]
            empty.alignment = ui.ALIGN_CENTER
            empty.frame = (8 + (card_width - 16) // 2, 26, (card_width - 16) // 2, 34)

            fill = "off" if snapshot["fill"] is None else "%s%%" % int(snapshot["fill"])
            meta = make_label(
                "%s  cap %s" % (fill, snapshot["capacity"]),
                font_size=10,
                color=COLORS["muted"],
            )
            meta.frame = (8, 58, card_width - 16, 14)

            for item in (tag, name, filled, empty, meta):
                self.add_subview(item)

    class SpacerCard(ui.View):
        """Empty grid cell to keep 6th St stations grouped (2x2 block)."""

        def __init__(self, card_width):
            super().__init__()
            self.background_color = COLORS["bg"]
            self.height = CARD_HEIGHT

    class SectionHeader(ui.View):
        def __init__(self, title):
            super().__init__()
            self.background_color = COLORS["bg"]
            self.height = SECTION_HEADER_HEIGHT
            label = make_label(title, font_size=13, bold=True, color=COLORS["muted"])
            label.frame = (0, 4, 300, 18)
            self.add_subview(label)

    def _measure_text(text, width, font_size=11, bold=False):
        label = make_label(str(text or ""), font_size=font_size, bold=bold, wrap=True)
        label.frame = (0, 0, max(1, width), 0)
        label.size_to_fit()
        return label.height

    def _train_row_height(train, card_width, *, by_line=False, index=0, line_badge=False, wrap_text=True, eta_column_width=None):
        if not wrap_text:
            return TRANSIT_LINE_ROW_HEIGHT if by_line else (28 if index == 0 else 24)
        eta_w = eta_column_width or ETA_COLUMN_WIDTH
        eta_size = 14 if by_line else (22 if index == 0 else 14)
        dest_size = 11 if by_line else (13 if index == 0 else 11)
        eta_bold = True if by_line or index == 0 else False
        dest_bold = by_line or index == 0
        from lib.subway_trains import format_train_eta

        eta_text = format_train_eta(train) if by_line else str(train.get("eta") or "?")
        dest_text = str(train.get("destination") or "?")
        eta_h = _measure_text(eta_text, eta_w, eta_size, eta_bold)
        line_x = 8 + eta_w - (4 if by_line else 0)
        if line_badge:
            line_x += 22
        dest_w = max(1, card_width - line_x - 8)
        dest_h = _measure_text(dest_text, dest_w, dest_size, dest_bold)
        base = TRANSIT_LINE_ROW_HEIGHT if by_line else (28 if index == 0 else 24)
        return max(base, eta_h + 2, dest_h + 4)

    def transit_card_height(board, card_width=300, wrap_text=True, eta_column_width=None):
        if board.get("tunnel_card"):
            rows = len(board.get("trains") or []) or 1
            header_h = 30
            if board.get("error") and not board.get("trains"):
                return header_h + 24
            return header_h + rows * TUNNEL_ROW_HEIGHT + 10

        inner_w = max(1, card_width - 16)
        if wrap_text and board.get("note"):
            note_h = _measure_text(board.get("note"), inner_w, 10) + 6
        else:
            note_h = 12 if board.get("note") else 0
        header_h = 28 + note_h
        if board.get("error"):
            return max(PATH_CARD_HEIGHT, header_h + 20)
        trains = board.get("trains") or []
        if not trains:
            return max(PATH_CARD_HEIGHT, header_h + 20)
        if board.get("by_line") is True:
            row_total = 0
            for train in trains:
                line_val = train.get("line")
                line_badge = line_val not in (None, "", "?")
                row_total += _train_row_height(
                    train,
                    card_width,
                    by_line=True,
                    line_badge=line_badge,
                    wrap_text=wrap_text,
                    eta_column_width=eta_column_width,
                )
            return max(PATH_CARD_HEIGHT, header_h + row_total + 10)
        row_total = 0
        for index, train in enumerate(trains[:3]):
            line_val = train.get("line")
            line_badge = line_val not in (None, "", "?")
            row_total += _train_row_height(
                train,
                card_width,
                by_line=False,
                index=index,
                line_badge=line_badge,
                wrap_text=wrap_text,
                eta_column_width=eta_column_width,
            )
        return max(PATH_CARD_HEIGHT, header_h + row_total + 8)

    def _add_line_badge(parent, line_val, x, y, size=18):
        from lib.subway_lines import subway_line_color, subway_line_text_color

        badge = ui.View()
        badge.background_color = subway_line_color(line_val)
        badge.corner_radius = 4
        badge.frame = (x, y, size, size)
        parent.add_subview(badge)
        label = make_label(
            str(line_val),
            font_size=11,
            bold=True,
            color=subway_line_text_color(line_val),
            align=ui.ALIGN_CENTER,
        )
        label.frame = (0, 1, size, size - 2)
        badge.add_subview(label)
        return size + 4

    class TransitCard(ui.View):
        def __init__(
            self,
            board,
            card_width,
            tag="NYC",
            empty_text="No trains",
            wrap_text=True,
            eta_column_width=None,
        ):
            super().__init__()
            self.background_color = COLORS["card"]
            self.corner_radius = 10
            self.border_width = 1
            self.border_color = "#2a3441"
            self._eta_w = eta_column_width or ETA_COLUMN_WIDTH
            self._wrap = wrap_text
            self.height = transit_card_height(
                board, card_width, wrap_text=self._wrap, eta_column_width=self._eta_w
            )

            name = make_label(board["label"], font_size=13, bold=True, wrap=False)
            name.frame = (8, 6, card_width - 56, 18)

            tag_text = "~" if board.get("estimated") else tag
            tag_label = make_label(tag_text, font_size=10, bold=True, color=COLORS["accent"], wrap=False)
            tag_label.alignment = ui.ALIGN_RIGHT
            tag_label.frame = (card_width - 44, 6, 36, 14)

            from lib.subway_trains import format_train_eta

            trains = sorted(
                board.get("trains") or [],
                key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999,
            )
            error = board.get("error")
            self.add_subview(name)
            self.add_subview(tag_label)
            y = 28
            if board.get("note"):
                note = make_label(board["note"], font_size=10, color=COLORS["muted"], wrap=self._wrap)
                if self._wrap:
                    note.frame = (8, 24, card_width - 16, 0)
                    note.size_to_fit()
                    y = 24 + note.height + 6
                else:
                    note.frame = (8, 24, card_width - 16, 12)
                    y = 36
                self.add_subview(note)
            if error:
                line = make_label("Unavailable", font_size=12, color=COLORS["bad"], wrap=False)
                line.frame = (8, y, card_width - 16, 16)
                self.add_subview(line)
                return
            if not trains:
                line = make_label(empty_text, font_size=12, color=COLORS["muted"], wrap=self._wrap)
                if self._wrap:
                    line.frame = (8, y, card_width - 16, 0)
                    line.size_to_fit()
                else:
                    line.frame = (8, y, card_width - 16, 16)
                self.add_subview(line)
                return

            if board.get("by_line") is True:
                for train in trains:
                    eta_text = format_train_eta(train)
                    dest_text = str(train.get("destination") or "?")
                    eta_color = COLORS["text"]
                    if train.get("status") == "DELAYED" or "delay" in eta_text.lower():
                        eta_color = COLORS["warn"]
                    line_val = train.get("line")
                    line_badge = line_val not in (None, "", "?")
                    row_h = _train_row_height(
                        train,
                        card_width,
                        by_line=True,
                        line_badge=line_badge,
                        wrap_text=self._wrap,
                    )
                    eta = make_label(eta_text, font_size=14, bold=True, color=eta_color, wrap=False)
                    eta.frame = (8, y, self._eta_w - 8, row_h)
                    line_x = 8 + self._eta_w - 4
                    if line_badge:
                        line_x += _add_line_badge(self, line_val, line_x, y + 1)
                    dest = make_label(dest_text, font_size=11, color=COLORS["muted"], wrap=self._wrap)
                    dest.frame = (line_x, y + 2, card_width - line_x - 8, 18 if not self._wrap else row_h - 2)
                    self.add_subview(eta)
                    self.add_subview(dest)
                    y += row_h
                return

            for index, train in enumerate(trains[:3]):
                eta_size = 22 if index == 0 else 14
                dest_size = 13 if index == 0 else 11
                eta_color = COLORS["text"] if index == 0 else COLORS["muted"]
                dest_color = COLORS["text"] if index == 0 else COLORS["muted"]
                eta_text = format_train_eta(train)
                dest_text = str(train.get("destination") or "?")
                if train.get("status") == "DELAYED" or "delay" in eta_text.lower():
                    eta_color = COLORS["warn"]
                line_val = train.get("line")
                line_badge = line_val not in (None, "", "?")
                row_h = _train_row_height(
                    train,
                    card_width,
                    by_line=False,
                    index=index,
                    line_badge=line_badge,
                    wrap_text=self._wrap,
                )
                eta = make_label(
                    eta_text,
                    font_size=eta_size,
                    bold=(index == 0),
                    color=eta_color,
                    wrap=False,
                )
                eta.frame = (8, y, self._eta_w, row_h)
                line_x = 8 + self._eta_w
                if line_badge:
                    line_x += _add_line_badge(self, line_val, line_x, y + (2 if index == 0 else 0))
                dest = make_label(
                    dest_text,
                    font_size=dest_size,
                    bold=(index == 0),
                    color=dest_color,
                    wrap=self._wrap,
                )
                dest_y = y + (2 if index == 0 else 0)
                dest_h = 20 if not self._wrap else row_h - 2
                dest.frame = (line_x, dest_y, card_width - line_x - 8, dest_h)
                self.add_subview(eta)
                self.add_subview(dest)
                y += row_h

    class TunnelCard(ui.View):
        def __init__(self, board, card_width):
            super().__init__()
            self.background_color = COLORS["card"]
            self.corner_radius = 10
            self.border_width = 1
            self.border_color = "#2a3441"
            self.height = transit_card_height(board, card_width)

            name = make_label(board["label"], font_size=15, bold=True)
            name.frame = (12, 8, card_width - 24, 20)
            self.add_subview(name)

            trains = board.get("trains") or []
            error = board.get("error")
            y = 34
            row_h = TUNNEL_ROW_HEIGHT
            if error and not trains:
                err = make_label("Unavailable", font_size=13, color=COLORS["bad"])
                err.frame = (12, y, card_width - 24, 18)
                self.add_subview(err)
                return

            for train in trains:
                row_w = card_width - 16
                row = ui.View()
                row.frame = (8, y, row_w, row_h - 4)
                row.background_color = "#151b22"
                row.corner_radius = 8
                self.add_subview(row)

                dest = make_label(str(train.get("destination") or "?"), font_size=14, bold=True)
                dest.frame = (10, 8, 110, 20)
                row.add_subview(dest)

                status = make_label(str(train.get("status_text") or ""), font_size=11, color=COLORS["muted"])
                status.frame = (row_w - 112, 12, 102, 16)
                status.alignment = ui.ALIGN_RIGHT
                row.add_subview(status)

                pill_w = 72
                pill = ui.View()
                pill.background_color = train.get("eta_bg") or COLORS["accent"]
                pill.corner_radius = 6
                pill.frame = (125, 6, pill_w, row_h - 16)
                row.add_subview(pill)

                eta = make_label(
                    str(train.get("eta") or "?"),
                    font_size=16,
                    bold=True,
                    color=train.get("eta_fg") or COLORS["text"],
                    align=ui.ALIGN_CENTER,
                )
                eta.frame = (0, 4, pill_w, row_h - 18)
                pill.add_subview(eta)
                y += row_h

    def _haptic_prolong_press():
        try:
            from objc_util import ObjCClass

            # UIImpactFeedbackStyleMedium
            gen = ObjCClass("UIImpactFeedbackGenerator").alloc().initWithStyle_(1)
            gen.prepare()
            gen.impactOccurred()
        except Exception:
            try:
                import sound

                sound.play_effect("ui:click")
            except Exception:
                pass

    class ProlongPill(ui.View):
        """Hold pauses the thumb-float countdown; release re-arms +5s."""

        def __init__(self, on_press, on_release):
            super().__init__()
            self.on_press = on_press
            self.on_release = on_release
            self.background_color = COLORS["accent"]
            self.corner_radius = 8
            self._holding = False
            self._title = make_label(
                "Prolong", font_size=14, bold=True, color=COLORS["text"], align=ui.ALIGN_CENTER
            )
            self.add_subview(self._title)

        @property
        def font(self):
            return self._title.font

        @font.setter
        def font(self, value):
            self._title.font = value

        def layout(self):
            self._title.frame = self.bounds

        def _set_holding_visual(self, holding):
            self.background_color = COLORS["bad"] if holding else COLORS["accent"]

        def _finish_hold(self):
            if not self._holding:
                return
            self._holding = False
            self._set_holding_visual(False)
            self.on_release()

        def touch_began(self, touch):
            self._holding = True
            self._set_holding_visual(True)
            _haptic_prolong_press()
            self.on_press()
            return True

        def touch_moved(self, touch):
            loc = touch.location
            if loc[0] < 0 or loc[1] < 0 or loc[0] > self.width or loc[1] > self.height:
                self._finish_hold()

        def touch_ended(self, touch):
            self._finish_hold()

        def touch_cancelled(self, touch):
            self._finish_hold()

    class BikeTrainTransitView(ui.View):
        def __init__(self):
            super().__init__()
            self.background_color = COLORS["bg"]
            self.name = APP_TITLE
            self._busy = False
            self._refresh_gen = 0
            self._active_tab = "from_jc"
            self._cache = {"snapshots": []}
            self._thumb_float_active = False
            self._thumb_float_gen = 0
            self._thumb_float_deadline = 0.0
            self._thumb_float_startup_pending = False
            self._prolong_visible = False
            self._prolong_hold_active = False

            self._float_layer = ui.View()
            self._float_layer.background_color = (0, 0, 0, 0)
            self._float_layer.touch_enabled = False
            self._float_layer.hidden = True

            self.prolong_btn = ProlongPill(self._prolong_press_began, self._prolong_press_ended)
            self.prolong_btn.hidden = True
            self._float_layer.add_subview(self.prolong_btn)

            self.header = ui.View()
            self.header.background_color = COLORS["bg"]

            self.title_label = make_label(APP_TITLE, font_size=24, bold=True)
            # Manual Refresh pill removed (v68) — data loads on kickoff + LAN refresh only.

            self.status_label = make_label("", font_size=12, color=COLORS["muted"])

            self.tab_bar = ui.View()
            self.tab_bar.background_color = COLORS["bg"]
            self.tab_cbike_btn = ui.Button(title="Cbike JC")
            self.tab_from_btn = ui.Button(title="From JC")
            self.tab_to_btn = ui.Button(title="To JC")
            self.tab_hblr_path_btn = ui.Button(title="HBLR↔PATH")
            self.tab_tunnels_btn = ui.Button(title="Tunnels")
            for btn in (
                self.tab_cbike_btn,
                self.tab_from_btn,
                self.tab_to_btn,
                self.tab_hblr_path_btn,
                self.tab_tunnels_btn,
            ):
                btn.corner_radius = 8
            self.tab_cbike_btn.action = self._tab_cbike_tapped
            self.tab_from_btn.action = self._tab_from_tapped
            self.tab_to_btn.action = self._tab_to_tapped
            self.tab_hblr_path_btn.action = self._tab_hblr_path_tapped
            self.tab_tunnels_btn.action = self._tab_tunnels_tapped
            self.tab_bar.add_subview(self.tab_cbike_btn)
            self.tab_bar.add_subview(self.tab_from_btn)
            self.tab_bar.add_subview(self.tab_to_btn)
            self.tab_bar.add_subview(self.tab_hblr_path_btn)
            self.tab_bar.add_subview(self.tab_tunnels_btn)

            self.scroll = ui.ScrollView()
            self.scroll.background_color = COLORS["bg"]
            self.scroll.shows_vertical_scroll_indicator = False

            self.header.add_subview(self.title_label)
            self.add_subview(self.header)
            self.add_subview(self.tab_bar)
            self.add_subview(self.status_label)
            self.add_subview(self.scroll)
            self.add_subview(self._float_layer)
            self._style_tabs()

        def _tab_buttons_ordered(self):
            return (
                self.tab_cbike_btn,
                self.tab_from_btn,
                self.tab_to_btn,
                self.tab_hblr_path_btn,
                self.tab_tunnels_btn,
            )

        def _thumb_float_buttons(self):
            """Bottom → top on screen: Tunnels (thumb), …, Prolong at top."""
            tabs = tuple(reversed(self._tab_buttons_ordered()))
            if self._prolong_visible:
                return tabs + (self.prolong_btn,)
            return tabs

        def _hide_prolong(self):
            self._prolong_visible = False
            self.prolong_btn.hidden = True

        def _show_prolong(self):
            self._prolong_visible = True
            self.prolong_btn.hidden = False

        def _rehome_button(self, btn, parent):
            if btn.superview is parent:
                return
            if btn.superview is not None:
                btn.superview.remove_subview(btn)
            parent.add_subview(btn)

        def _restore_docked_chrome(self):
            for btn in self._tab_buttons_ordered():
                self._rehome_button(btn, self.tab_bar)
            self._hide_prolong()
            for btn in self._tab_buttons_ordered():
                btn.corner_radius = 8

        def _layout_insets(self):
            """Safe area for iPhone 12+ notch / Dynamic Island / home indicator."""
            try:
                ins = self.safe_area_insets
                top = max(TOP_CONTENT_INSET, int(ins.top))
                return int(ins.left), top, int(ins.right), int(ins.bottom)
            except Exception:
                return 0, TOP_CONTENT_INSET, 0, 34

        def _thumb_float_scale(self, width, height):
            left, top, right, bottom = self._layout_insets()
            usable_w = max(width - left - right, PHONE6_REF_W)
            usable_h = max(height - top - bottom, PHONE6_REF_USABLE_H)
            w_scale = usable_w / float(PHONE6_REF_W)
            h_scale = usable_h / float(PHONE6_REF_USABLE_H)
            return min(THUMB_FLOAT_SCALE_MAX, max(0.96, min(w_scale, h_scale)))

        def _thumb_float_sizes(self, width, height):
            scale = self._thumb_float_scale(width, height)
            tab_w = max(92, int(THUMB_FLOAT_TAB_W_BASE * scale))
            prolong_w = max(100, int(THUMB_PROLONG_W_BASE * scale))
            btn_h = max(46, int(THUMB_FLOAT_BTN_H_BASE * scale))
            return tab_w, prolong_w, btn_h

        def _thumb_float_fonts(self, width, height):
            scale = self._thumb_float_scale(width, height)
            tab = max(12, int(round(13 * scale)))
            prolong = max(13, int(round(14 * scale)))
            return tab, prolong

        def _thumb_float_column_center_x(self, width, max_btn_w):
            """Shared vertical axis; clamped so the widest pill stays on-screen."""
            left, top, right, bottom = self._layout_insets()
            usable_w = width - left - right
            edge = THUMB_FLOAT_MARGIN_EDGE
            center_x = left + int(usable_w * THUMB_FLOAT_STACK_X_RATIO)
            half = max_btn_w // 2
            lo = left + edge + half
            hi = width - right - edge - half
            return max(lo, min(center_x, hi))

        def _thumb_float_stack_x(self, width, btn_w, column_center_x):
            return int(column_center_x - btn_w / 2)

        def _float_layer_frame(self, width, height):
            pad = 10
            frames = self._thumb_float_screen_frames(width, height)
            if not frames:
                return (0, 0, width, height // 2)
            min_x = min(f[0] for f in frames.values())
            min_y = min(f[1] for f in frames.values())
            max_x = max(f[0] + f[2] for f in frames.values())
            max_y = max(f[1] + f[3] for f in frames.values())
            layer_x = max(0, min_x - pad)
            layer_y = max(0, min_y - pad)
            layer_w = min(width - layer_x, max_x - min_x + pad * 2)
            layer_h = min(height - layer_y, max_y - min_y + pad * 2)
            return (layer_x, layer_y, layer_w, layer_h)

        def _thumb_float_screen_frames(self, width, height):
            """Vertical pill stack toward screen center (left-hand thumb on ~6 inch screens)."""
            left, top, right, bottom = self._layout_insets()
            usable_h = height - top - bottom
            tab_w, prolong_w, btn_h = self._thumb_float_sizes(width, height)
            buttons = self._thumb_float_buttons()
            gap = THUMB_FLOAT_BTN_GAP
            widths = [
                prolong_w if btn is self.prolong_btn else tab_w for btn in buttons
            ]
            count = len(buttons)
            total_h = count * btn_h + max(0, count - 1) * gap
            column_center_x = self._thumb_float_column_center_x(width, max(widths))
            stack_center_y = top + int(usable_h * THUMB_FLOAT_STACK_Y_RATIO)
            start_y = stack_center_y - total_h // 2
            min_y = top + 8
            max_y = top + usable_h - THUMB_FLOAT_MARGIN_BOTTOM - total_h
            start_y = max(min_y, min(start_y, max_y))
            frames = {}
            y = start_y + total_h - btn_h
            for btn, btn_w in zip(buttons, widths):
                x = self._thumb_float_stack_x(width, btn_w, column_center_x)
                frames[btn] = (x, int(y), btn_w, btn_h)
                y -= btn_h + gap
            return frames

        def _thumb_float_frames(self, width, height):
            layer_x, layer_y, layer_w, layer_h = self._float_layer_frame(width, height)
            return {
                btn: (sx - layer_x, sy - layer_y, fw, fh)
                for btn, (sx, sy, fw, fh) in self._thumb_float_screen_frames(
                    width, height
                ).items()
            }

        def _layout_thumb_float(self):
            if not self.width or not self.height:
                return
            self._float_layer.frame = self._float_layer_frame(self.width, self.height)
            for btn, frame in self._thumb_float_frames(self.width, self.height).items():
                btn.frame = frame
                btn.corner_radius = min(frame[3], frame[2]) / 2
            if self._prolong_visible:
                _, prolong_pt = self._thumb_float_fonts(self.width, self.height)
                self.prolong_btn.font = ("<system-bold>", prolong_pt)
                self.prolong_btn.hidden = False
            else:
                self.prolong_btn.hidden = True

        def _bump_thumb_float_gen(self):
            self._thumb_float_gen += 1

        def _check_thumb_float_expired(self):
            if not self._thumb_float_active or self._busy or self._prolong_hold_active:
                return
            # deadline <= 0 means timer not armed yet (waiting for refresh to finish).
            if self._thumb_float_deadline <= 0:
                return
            if time.monotonic() >= self._thumb_float_deadline:
                log_event("thumb float dock (timeout)")
                self._exit_thumb_float()

        def _schedule_thumb_float_tick(self):
            self._bump_thumb_float_gen()
            gen = self._thumb_float_gen

            def _tick():
                if gen != self._thumb_float_gen or not self._thumb_float_active:
                    return
                if self._thumb_float_deadline <= 0:
                    ui.delay(_tick, 0.2)
                    return
                if self._prolong_hold_active:
                    ui.delay(_tick, 0.2)
                    return
                if time.monotonic() >= self._thumb_float_deadline:
                    if not self._busy:
                        self._exit_thumb_float()
                    else:
                        ui.delay(_tick, 0.2)
                    return
                ui.delay(_tick, 0.2)

            ui.delay(_tick, 0.2)

        def _arm_thumb_float_timer(self):
            self._thumb_float_deadline = time.monotonic() + THUMB_FLOAT_SEC
            if self._thumb_float_active:
                log_event("thumb float armed {}s".format(int(THUMB_FLOAT_SEC)))
                self._schedule_thumb_float_tick()

        def _maybe_arm_thumb_float_timer(self):
            if self._thumb_float_active and not self._busy:
                self._arm_thumb_float_timer()

        def _move_tabs_to_float_layer(self):
            for btn in self._tab_buttons_ordered():
                self._rehome_button(btn, self._float_layer)

        def _enter_startup_thumb_float(self):
            """Startup only — arm float once layout() has real dimensions."""
            self._thumb_float_startup_pending = True
            self._maybe_enter_startup_thumb_float()

        def _maybe_enter_startup_thumb_float(self):
            if not self._thumb_float_startup_pending or self._thumb_float_active:
                return
            if not self.width or not self.height:
                return
            self._thumb_float_startup_pending = False
            self._thumb_float_active = True
            self._thumb_float_deadline = 0.0
            self._show_prolong()
            self._float_layer.hidden = False
            self._float_layer.touch_enabled = True
            self._move_tabs_to_float_layer()
            self._layout_thumb_float()
            self._style_tabs()
            self._float_layer.bring_to_front()
            self._maybe_arm_thumb_float_timer()

        def _prolong_press_began(self):
            if not self._prolong_visible or not self._thumb_float_active:
                return
            self._prolong_hold_active = True

        def _prolong_press_ended(self):
            if not self._prolong_hold_active:
                return
            self._prolong_hold_active = False
            if not self._prolong_visible:
                return
            log_event("thumb float prolong +{}s".format(int(THUMB_FLOAT_SEC)))
            self._arm_thumb_float_timer()

        def _exit_thumb_float(self, repaint=True):
            self._prolong_hold_active = False
            if not self._thumb_float_active:
                return
            self._thumb_float_active = False
            self._hide_prolong()
            self._bump_thumb_float_gen()
            self._float_layer.hidden = True
            self._float_layer.touch_enabled = False
            self._restore_docked_chrome()
            self.layout()
            if not repaint:
                return
            try:
                self._paint_active_tab()
            except Exception as exc:
                log_event("Tab repaint after dock failed: {}".format(exc))
                log_event(traceback.format_exc())

        def _dock_and_select_tab(self, tab):
            try:
                self._exit_thumb_float(repaint=False)
                self._set_tab(tab, force=True)
            except Exception as exc:
                log_event("section tap dock failed: {}".format(exc))
                log_event(traceback.format_exc())

        def start_remote_poll(self):
            self._poll_remote_control()

        def _style_tabs(self):
            tab_pt, _ = (
                self._thumb_float_fonts(self.width, self.height)
                if self._thumb_float_active and self.width and self.height
                else (13, 14)
            )
            busy = self._busy
            for tab, btn in (
                ("cbike_jc", self.tab_cbike_btn),
                ("from_jc", self.tab_from_btn),
                ("to_jc", self.tab_to_btn),
                ("hblr_path", self.tab_hblr_path_btn),
                ("tunnels", self.tab_tunnels_btn),
            ):
                btn.enabled = not busy
                if busy:
                    btn.background_color = TAB_BUSY_BG
                    btn.tint_color = COLORS["muted"]
                    btn.font = (
                        ("<system>", tab_pt)
                        if self._thumb_float_active
                        else ("<system>", 14)
                    )
                    continue
                is_active = self._active_tab == tab
                btn.background_color = COLORS["accent"] if is_active else "#2a3441"
                btn.tint_color = COLORS["text"]
                if self._thumb_float_active:
                    btn.font = ("<system-bold>", tab_pt) if is_active else ("<system>", tab_pt)
                else:
                    btn.font = ("<system-bold>", 14) if is_active else ("<system>", 14)

        def _acknowledge_float_pill_tap(self, tab):
            """Immediate visual feedback before deferred dock/paint (main thread)."""
            if not self._thumb_float_active:
                return
            tab_pt, _ = (
                self._thumb_float_fonts(self.width, self.height)
                if self.width and self.height
                else (13, 14)
            )
            for name, btn in (
                ("cbike_jc", self.tab_cbike_btn),
                ("from_jc", self.tab_from_btn),
                ("to_jc", self.tab_to_btn),
                ("hblr_path", self.tab_hblr_path_btn),
                ("tunnels", self.tab_tunnels_btn),
            ):
                tapped = name == tab
                btn.background_color = (
                    THUMB_FLOAT_TAP_HIGHLIGHT if tapped else "#2a3441"
                )
                btn.tint_color = COLORS["text"]
                btn.font = ("<system-bold>", tab_pt) if tapped else ("<system>", tab_pt)

        def _set_tab(self, tab, force=False):
            if self._active_tab == tab and not force:
                return
            self._active_tab = tab
            try:
                from lib import app_state

                app_state.set_active_tab(tab)
            except Exception:
                pass
            self._style_tabs()
            try:
                self._paint_active_tab()
            except Exception as exc:
                log_event("Tab paint failed: {}".format(exc))
                log_event(traceback.format_exc())
                self.status_label.text = "UI error: %s" % exc

        def _on_section_tap(self, tab):
            if self._busy:
                return
            if self._thumb_float_active:
                self._acknowledge_float_pill_tap(tab)
                ui.delay(lambda: self._dock_and_select_tab(tab), 0)
                return
            self._set_tab(tab)

        def _tab_cbike_tapped(self, sender):
            self._on_section_tap("cbike_jc")

        def _tab_from_tapped(self, sender):
            self._on_section_tap("from_jc")

        def _tab_to_tapped(self, sender):
            self._on_section_tap("to_jc")

        def _tab_hblr_path_tapped(self, sender):
            self._on_section_tap("hblr_path")

        def _tab_tunnels_tapped(self, sender):
            self._on_section_tap("tunnels")

        def _poll_remote_control(self):
            import ui

            try:
                from lib.app_control import clear_control, is_refresh_requested

                if is_refresh_requested():
                    if self._busy:
                        log_event("LAN refresh queued (busy)")
                    else:
                        clear_control()
                        log_event("LAN refresh requested")
                        self.refresh()
            except Exception:
                pass
            self._check_thumb_float_expired()
            ui.delay(self._poll_remote_control, 1.0)

        def layout(self):
            try:
                self._maybe_enter_startup_thumb_float()
                left, top, right, bottom = self._layout_insets()
                width = self.width
                height = self.height
                header_h = 64 + top
                tab_top = header_h + 2
                status_top = tab_top + TAB_BAR_HEIGHT + 2

                self.header.frame = (0, 0, width, header_h)
                self.title_label.frame = (16, top + 8, width - 32, 28)
                self.tab_bar.frame = (0, tab_top, width, TAB_BAR_HEIGHT)
                tab_gap = 4
                tab_side = 6
                tab_count = 5
                tab_w = max((width - tab_side * 2 - tab_gap * (tab_count - 1)) // tab_count, 64)
                tab_btns = (
                    self.tab_cbike_btn,
                    self.tab_from_btn,
                    self.tab_to_btn,
                    self.tab_hblr_path_btn,
                    self.tab_tunnels_btn,
                )
                if self._thumb_float_active:
                    self._float_layer.hidden = False
                    self._float_layer.touch_enabled = True
                    self._layout_thumb_float()
                    self._style_tabs()
                    self._float_layer.bring_to_front()
                else:
                    self._float_layer.hidden = True
                    self._hide_prolong()
                    if self.tab_cbike_btn.superview is not self.tab_bar:
                        self._restore_docked_chrome()
                    for index, btn in enumerate(tab_btns):
                        btn.frame = (
                            tab_side + index * (tab_w + tab_gap),
                            0,
                            tab_w,
                            TAB_BAR_HEIGHT - 4,
                        )
                        btn.font = ("<system>", 12)
                self.status_label.frame = (16, status_top, width - 32, 16)
                scroll_bottom = max(bottom, 8)
                self.scroll.frame = (
                    0,
                    status_top + 20,
                    width,
                    max(0, height - status_top - 20 - scroll_bottom),
                )
            except Exception as exc:
                log_event("layout failed: {}".format(exc))
                log_event(traceback.format_exc())

        def _apply_refresh_payload(self, payload):
            from lib import app_state

            refresh_id = payload.get("refresh_id")
            if refresh_id != self._refresh_gen:
                log_event("step: stale refresh #{} apply skipped".format(refresh_id))
                return

            if payload.get("error"):
                app_state.set_error(payload["error"])
                self.status_label.text = "Error: %s" % payload["error"]
                return

            try:
                log_event("step: finish render start")
                self.render_snapshots(
                    payload["snapshots"],
                    payload["path_boards"],
                    payload["path_33rd_boards"],
                    payload["subway_boards"],
                    payload["path_nj_boards"],
                    payload["subway_to_jc_boards"],
                    payload["tunnel_boards"],
                    payload["hblr_path_sections"],
                    path_exchange_wtc=payload["path_exchange_wtc"],
                    subway_wtc_north=payload["subway_wtc_north"],
                )
                log_event("step: finish render done")
            except Exception as exc:
                app_state.set_error(str(exc))
                self.status_label.text = "Error: %s" % exc
                log_event("UI finish failed: {}".format(exc))
                log_event(traceback.format_exc())

        def _finish_refresh(self, refresh_id):
            if refresh_id != self._refresh_gen:
                return
            from lib import app_state

            self._busy = False
            app_state.set_busy(False)
            self._style_tabs()
            if self._thumb_float_active:
                self._arm_thumb_float_timer()

        def _refresh_step_transit(self, refresh_id, payload):
            """Main thread only — no @ui.in_background (Pythonista TLS crash)."""
            if refresh_id != self._refresh_gen:
                return
            if not self._busy:
                log_event("step: transit #{} skipped (not busy)".format(refresh_id))
                return
            try:
                log_event("step: fetch transit")
                (
                    payload["path_boards"],
                    payload["path_33rd_boards"],
                    payload["subway_boards"],
                    payload["path_nj_boards"],
                    payload["subway_to_jc_boards"],
                    payload["tunnel_boards"],
                    payload["hblr_path_sections"],
                    payload["path_exchange_wtc"],
                    payload["subway_wtc_north"],
                ) = _fetch_transit_boards()
                log_event("step: transit ok")
            except Exception as exc:
                log_event("Transit fetch failed: {}".format(exc))
                log_event(traceback.format_exc())

            if refresh_id != self._refresh_gen:
                log_event("step: stale fetch #{} discarded".format(refresh_id))
                self._finish_refresh(refresh_id)
                return

            try:
                self._apply_refresh_payload(payload)
            finally:
                self._finish_refresh(refresh_id)

        def _refresh_step_bikes(self, refresh_id):
            """Main thread only — fetch GBFS, then yield before transit."""
            if refresh_id != self._refresh_gen:
                return
            if not self._busy:
                log_event("step: bikes #{} skipped (not busy)".format(refresh_id))
                return
            payload = {
                "refresh_id": refresh_id,
                "error": None,
                "snapshots": None,
                "path_boards": [],
                "path_33rd_boards": [],
                "subway_boards": [],
                "path_nj_boards": [],
                "subway_to_jc_boards": [],
                "tunnel_boards": [],
                "hblr_path_sections": [],
                "path_exchange_wtc": None,
                "subway_wtc_north": [],
            }
            try:
                log_event("step: fetch bikes")
                payload["snapshots"] = get_snapshots()
                log_event("step: bikes ok ({})".format(len(payload["snapshots"] or [])))
            except Exception as exc:
                payload["error"] = str(exc)
                log_event("Refresh failed: {}".format(payload["error"]))
                log_event(traceback.format_exc())
                try:
                    self._apply_refresh_payload(payload)
                finally:
                    self._finish_refresh(refresh_id)
                return

            if refresh_id != self._refresh_gen:
                log_event("step: stale fetch #{} discarded".format(refresh_id))
                self._finish_refresh(refresh_id)
                return

            ui.delay(lambda: self._refresh_step_transit(refresh_id, payload), 0.05)

        def refresh(self):
            if self._busy:
                log_event("refresh skipped (busy)")
                return
            from lib import app_state
            from lib.http_cache import reset_stats

            self._refresh_gen += 1
            refresh_id = self._refresh_gen
            self._busy = True
            app_state.set_busy(True)
            self._style_tabs()
            self.status_label.text = "Updating..." + _cache_ttl_suffix()
            log_event("Refresh started (#{})".format(refresh_id))
            reset_stats()
            ui.delay(lambda: self._refresh_step_bikes(refresh_id), 0.05)

        def _log_transit_boards(self, prefix, boards):
            if not boards:
                return
            for board in boards:
                if board.get("error"):
                    log_event("{} {} unavailable: {}".format(prefix, board["label"], board["error"]))
                    continue
                if prefix == "HBLRPATH":
                    source = board.get("source") or ("pdf" if board.get("estimated") else "live")
                    note = board.get("note")
                    if source != "transit" or note:
                        log_event(
                            "{} {} [{}]{}".format(
                                prefix,
                                board["label"],
                                source,
                                (" · %s" % note) if note else "",
                            )
                        )
                for train in board.get("trains") or []:
                    line = train.get("line")
                    line_text = " %s" % line if line else ""
                    log_event(
                        "{} {} -> {}{} {}".format(
                            prefix,
                            board["label"],
                            train["eta"],
                            line_text,
                            train["destination"],
                        )
                    )

        def _append_transit_section(self, y, pad, inner_w, card_width, title, boards, tag, empty_text):
            if boards is None:
                return y
            header = SectionHeader(title)
            header.frame = (pad, y, inner_w, SECTION_HEADER_HEIGHT)
            self.scroll.add_subview(header)
            y += SECTION_HEADER_HEIGHT + CARD_GAP
            cols = CARD_COLUMNS
            if not boards:
                return y + pad
            row_heights = []
            row_boards = []
            for index, board in enumerate(boards):
                col = index % cols
                if col == 0:
                    row_heights.append(transit_card_height(board, card_width))
                    row_boards.append([])
                else:
                    row_heights[-1] = max(row_heights[-1], transit_card_height(board, card_width))
                row_boards[-1].append((index, board))

            row_y = y
            for row_index, group in enumerate(row_boards):
                row_h = row_heights[row_index]
                for index, board in group:
                    col = index % cols
                    x = pad + col * (card_width + CARD_GAP)
                    card = TransitCard(board, card_width, tag=tag, empty_text=empty_text)
                    card.frame = (x, row_y, card_width, row_h)
                    self.scroll.add_subview(card)
                row_y += row_h + CARD_GAP
            return row_y + pad - CARD_GAP

        def _pick_board(self, boards, label, by_line=False):
            for board in boards or []:
                if board.get("label") == label:
                    return board
            stub = {"label": label, "trains": [], "error": None}
            if by_line:
                stub["by_line"] = True
            return stub

        def _append_tile_row(self, y, pad, inner_w, card_width, tiles, wrap_text=True):
            """tiles: list of (board, tag, empty_text). Two columns per row."""
            if not tiles:
                return y
            cols = CARD_COLUMNS
            row_groups = []
            row_heights = []
            for index, tile in enumerate(tiles):
                board = tile[0]
                tag = tile[1]
                col = index % cols
                tile_wrap = tile[3] if len(tile) > 3 else wrap_text
                board_wrap = tile_wrap
                eta_w = (
                    HBLR_PATH_ETA_WIDTH
                    if (not board_wrap and tag in ("PATH", "↑"))
                    else None
                )
                if col == 0:
                    row_groups.append([])
                    row_heights.append(
                        transit_card_height(
                            board, card_width, wrap_text=board_wrap, eta_column_width=eta_w
                        )
                    )
                else:
                    row_heights[-1] = max(
                        row_heights[-1],
                        transit_card_height(
                            board, card_width, wrap_text=board_wrap, eta_column_width=eta_w
                        ),
                    )
                row_groups[-1].append((index, tile, eta_w, board_wrap))

            row_y = y
            for row_index, group in enumerate(row_groups):
                row_h = row_heights[row_index]
                for index, tile, eta_w, board_wrap in group:
                    board = tile[0]
                    tag = tile[1]
                    empty_text = tile[2] if len(tile) > 2 else "No trains"
                    col = index % cols
                    x = pad + col * (card_width + CARD_GAP)
                    resolved_empty = empty_text or board.get("empty_hint") or "No trains"
                    card = TransitCard(
                        board,
                        card_width,
                        tag=tag,
                        empty_text=resolved_empty,
                        wrap_text=board_wrap,
                        eta_column_width=eta_w,
                    )
                    card.frame = (x, row_y, card_width, row_h)
                    self.scroll.add_subview(card)
                row_y += row_h + CARD_GAP
            return row_y

        def _paint_via_wtc_subway_section(self, y, pad, inner_w, card_width):
            """Exchange PATH (raw) + northbound WTC subway after LSP/Exchange chain."""
            header = SectionHeader("PATH + Subway via WTC")
            header.frame = (pad, y, inner_w, SECTION_HEADER_HEIGHT)
            self.scroll.add_subview(header)
            y += SECTION_HEADER_HEIGHT + CARD_GAP

            path_exchange = self._cache.get("path_exchange_wtc")
            if path_exchange:
                y = self._append_tile_row(
                    y,
                    pad,
                    inner_w,
                    card_width,
                    [(path_exchange, "PATH", "No WTC trains")],
                    wrap_text=False,
                )
                y += CARD_GAP

            wtc_north = self._cache.get("subway_wtc_north") or []
            tiles = (
                (
                    self._pick_board(wtc_north, "WTC Cortlandt", by_line=True),
                    "↑",
                    "None catchable",
                ),
                (
                    self._pick_board(wtc_north, "WTC", by_line=True),
                    "↑",
                    "None catchable",
                ),
            )
            y = self._append_tile_row(y, pad, inner_w, card_width, tiles, wrap_text=False)
            return y + SECTION_GAP

        def _append_from_jc_transit(self, y, pad, inner_w, card_width):
            y = self._append_transit_section(
                y,
                pad,
                inner_w,
                card_width,
                "PATH → NYC",
                self._cache.get("path_boards"),
                tag="NYC",
                empty_text="No NYC trains",
            )
            y += SECTION_GAP

            header = SectionHeader("PATH + Subway · 33rd St")
            header.frame = (pad, y, inner_w, SECTION_HEADER_HEIGHT)
            self.scroll.add_subview(header)
            y += SECTION_HEADER_HEIGHT + CARD_GAP

            path33 = self._cache.get("path_33rd_boards")
            subway = self._cache.get("subway_boards")

            groups = (
                [
                    (self._pick_board(path33, "Chris St"), "33", "No 33rd St"),
                    (self._pick_board(subway, "Chris St", by_line=True), "↑", "None catchable"),
                ],
                [
                    (self._pick_board(path33, "9th St"), "33", "No 33rd St"),
                    (self._pick_board(subway, "West 4 St", by_line=True), "↑", "None catchable"),
                ],
                [
                    (self._pick_board(path33, "14 St PATH"), "33", "No 33rd St"),
                    (self._pick_board(subway, "6 Av", by_line=True), "↑", "None catchable"),
                    (self._pick_board(subway, "14 St - Union Sq", by_line=True), "↑", "None catchable"),
                ],
                [
                    (self._pick_board(subway, "51 St", by_line=True), "↑", None),
                    (self._pick_board(subway, "50 St", by_line=True), "↑", None),
                ],
                [
                    (self._pick_board(subway, "Bleecker St", by_line=True), "↓", None),
                ],
            )
            for group in groups:
                y = self._append_tile_row(
                    y, pad, inner_w, card_width, group, wrap_text=False
                )
                y += CARD_GAP
            return y + pad

        def render_snapshots(
            self,
            snapshots,
            path_boards=None,
            path_33rd_boards=None,
            subway_boards=None,
            path_nj_boards=None,
            subway_to_jc_boards=None,
            tunnel_boards=None,
            hblr_path_sections=None,
            path_exchange_wtc=None,
            subway_wtc_north=None,
            partial=False,
        ):
            from lib import app_state

            if snapshots is not None:
                self._cache["snapshots"] = snapshots
            if not partial:
                self._cache["path_boards"] = path_boards
                self._cache["path_33rd_boards"] = path_33rd_boards
                self._cache["subway_boards"] = subway_boards
                self._cache["path_nj_boards"] = path_nj_boards
                self._cache["subway_to_jc_boards"] = subway_to_jc_boards
                self._cache["tunnel_boards"] = tunnel_boards
                self._cache["hblr_path_sections"] = hblr_path_sections
                self._cache["path_exchange_wtc"] = path_exchange_wtc
                self._cache["subway_wtc_north"] = subway_wtc_north
                for snapshot in snapshots or []:
                    log_event(
                        "{} filled={} empty={}".format(
                            tagged_name(snapshot), snapshot["bikes"], snapshot["docks"]
                        )
                    )
                self._log_transit_boards("PATH", path_boards)
                self._log_transit_boards("PATH33", path_33rd_boards)
                self._log_transit_boards("PATHNJ", path_nj_boards)
                self._log_transit_boards("SUBWAY", subway_boards)
                self._log_transit_boards("SUBWAYJC", subway_to_jc_boards)
                self._log_transit_boards("TUNNEL", tunnel_boards)
                for section in hblr_path_sections or []:
                    if section.get("layout") == "shared_primary":
                        self._log_transit_boards("HBLRPATH", [section.get("primary")])
                        for conn in section.get("connections") or []:
                            self._log_transit_boards("HBLRPATH", [conn.get("board")])
                    else:
                        for key in ("primary", "secondary"):
                            self._log_transit_boards("HBLRPATH", [section.get(key)])
                if path_exchange_wtc or subway_wtc_north:
                    if path_exchange_wtc:
                        self._log_transit_boards("HBLRPATH", [path_exchange_wtc])
                    self._log_transit_boards("HBLRPATH", subway_wtc_north)
                log_event("Refresh OK: {} stations".format(len(snapshots or [])))
                app_state.update_refresh(
                    snapshots or self._cache.get("snapshots") or [],
                    path_boards,
                    subway_boards,
                    path_33rd_boards,
                    path_nj_boards,
                    subway_to_jc_boards,
                    tunnel_boards=tunnel_boards,
                    active_tab=self._active_tab,
                    tagged_name_fn=tagged_name,
                )
            self._paint_active_tab(partial=partial)

        def _paint_active_tab(self, partial=False):
            import ui

            for subview in list(self.scroll.subviews):
                self.scroll.remove_subview(subview)
            width = max(self.width - 16, 320)
            pad = 8
            inner_w = width - pad * 2
            card_width = (inner_w - CARD_GAP * (CARD_COLUMNS - 1)) // CARD_COLUMNS
            try:
                if self._active_tab == "cbike_jc":
                    y = self._paint_cbike_jc(pad, inner_w, card_width, partial=partial)
                elif self._active_tab == "to_jc":
                    y = self._paint_to_jc(pad, inner_w, card_width, partial=partial)
                elif self._active_tab == "hblr_path":
                    y = self._paint_hblr_path(pad, inner_w, card_width, partial=partial)
                elif self._active_tab == "tunnels":
                    y = self._paint_tunnels(pad, inner_w, card_width, partial=partial)
                else:
                    y = self._paint_from_jc(pad, inner_w, card_width, partial=partial)
                content_h = max(y, pad)
                self.scroll.content_size = (width, content_h)
                if content_h <= self.scroll.height:
                    self.scroll.content_offset = (0, 0)
                if not partial:
                    tab_labels = {
                        "cbike_jc": "Cbike JC",
                        "from_jc": REGION,
                        "to_jc": "To JC",
                        "hblr_path": "JC HBLR ↔ PATH",
                        "tunnels": "Tunnels",
                    }
                    self.status_label.text = "Updated %s · %s%s" % (
                        datetime.now().strftime("%I:%M:%S %p"),
                        tab_labels.get(self._active_tab, REGION),
                        _cache_ttl_suffix(),
                    )
            except Exception as exc:
                log_event("Paint failed: {}".format(exc))
                log_event(traceback.format_exc())
                self.status_label.text = "UI error: %s" % exc

        def _paint_cbike_jc(self, pad, inner_w, card_width, partial=False):
            snapshots = self._cache.get("snapshots") or []
            rows = (len(GRID_SLOTS) + CARD_COLUMNS - 1) // CARD_COLUMNS
            for index, slot in enumerate(GRID_SLOTS):
                col = index % CARD_COLUMNS
                row = index // CARD_COLUMNS
                x = pad + col * (card_width + CARD_GAP)
                card_y = pad + row * (CARD_HEIGHT + CARD_GAP)
                if slot is None:
                    card = SpacerCard(card_width)
                elif slot < len(snapshots):
                    card = StationCard(snapshots[slot], card_width)
                else:
                    card = StationCard(_placeholder_snapshot("No data"), card_width)
                card.frame = (x, card_y, card_width, CARD_HEIGHT)
                self.scroll.add_subview(card)
            return pad + rows * CARD_HEIGHT + max(0, rows - 1) * CARD_GAP + pad

        def _paint_from_jc(self, pad, inner_w, card_width, partial=False):
            if partial:
                return pad
            return self._append_from_jc_transit(pad, pad, inner_w, card_width)

        def _paint_to_jc(self, pad, inner_w, card_width, partial=False):
            if partial:
                return pad

            y = pad
            subway_boards = self._cache.get("subway_to_jc_boards") or []
            path_nj_boards = self._cache.get("path_nj_boards") or []
            wtc_path = self._pick_board(path_nj_boards, "WTC")
            path_nj_rest = [
                board for board in path_nj_boards if board.get("label") != "WTC"
            ]

            header = SectionHeader("Subway + PATH . Nwk")
            header.frame = (pad, y, inner_w, SECTION_HEADER_HEIGHT)
            self.scroll.add_subview(header)
            y += SECTION_HEADER_HEIGHT + CARD_GAP

            nwk_tiles = [(board, "↓", "No downtown trains") for board in subway_boards]
            nwk_tiles.append((wtc_path, "NJ", "No NJ trains"))
            y = self._append_tile_row(y, pad, inner_w, card_width, nwk_tiles)
            y += SECTION_GAP

            y = self._append_transit_section(
                y,
                pad,
                inner_w,
                card_width,
                "PATH → NJ",
                path_nj_rest,
                tag="NJ",
                empty_text="No NJ trains",
            )
            return y

        def _paint_hblr_path(self, pad, inner_w, card_width, partial=False):
            if partial:
                return pad

            y = pad
            sections = self._cache.get("hblr_path_sections") or []
            for section in sections:
                header = SectionHeader(section.get("title") or "HBLR ↔ PATH")
                header.frame = (pad, y, inner_w, SECTION_HEADER_HEIGHT)
                self.scroll.add_subview(header)
                y += SECTION_HEADER_HEIGHT + CARD_GAP

                if section.get("layout") == "shared_primary":
                    primary = section.get("primary") or {}
                    card_h = transit_card_height(primary, inner_w, wrap_text=False)
                    card = TransitCard(
                        primary,
                        inner_w,
                        tag="HBLR",
                        empty_text="No departures",
                        wrap_text=False,
                    )
                    card.frame = (pad, y, inner_w, card_h)
                    self.scroll.add_subview(card)
                    y += card_h + CARD_GAP

                    tiles = []
                    for conn in section.get("connections") or []:
                        board = dict(conn.get("board") or {})
                        tiles.append((board, "PATH", "None catchable"))
                    y = self._append_tile_row(
                        y, pad, inner_w, card_width, tiles, wrap_text=False
                    )
                    y = self._paint_via_wtc_subway_section(y, pad, inner_w, card_width)
                    continue

                primary = section.get("primary") or {}
                secondary = section.get("secondary") or {}
                primary_tag = "HBLR" if primary.get("by_line") is True else "PATH"
                secondary_tag = "HBLR" if secondary.get("by_line") is True else "PATH"

                y = self._append_tile_row(
                    y,
                    pad,
                    inner_w,
                    card_width,
                    [
                        (primary, primary_tag, "No departures"),
                        (secondary, secondary_tag, "None catchable"),
                    ],
                    wrap_text=False,
                )
                y += SECTION_GAP
            return y + pad

        def _paint_tunnels(self, pad, inner_w, card_width, partial=False):
            if partial:
                return pad

            y = pad
            boards = self._cache.get("tunnel_boards") or []
            for board in boards:
                card = TunnelCard(board, inner_w)
                card.frame = (pad, y, inner_w, card.height)
                self.scroll.add_subview(card)
                y += card.height + CARD_GAP
            return y + pad

    def _needs_ui_handoff():
        try:
            from lib.shortcut_launcher import URL_LAUNCH_ENV

            if os.environ.pop(URL_LAUNCH_ENV, None):
                return True
        except ImportError:
            if os.environ.pop("BIKE_TRAIN_TRANSIT_URL_LAUNCH", None):
                return True
        try:
            import appex

            return appex.is_running_extension()
        except ImportError:
            return False

    def _kickoff_ui(view):
        """Start polling and first refresh once the UI run loop is active."""
        try:
            from lib.app_control import clear_control

            clear_control()
            log_event("kickoff: poll + first refresh")
            view.start_remote_poll()
            view.status_label.text = "Starting..." + _cache_ttl_suffix()
            view._enter_startup_thumb_float()
            view.refresh()
        except Exception as exc:
            log_event("kickoff failed: {}".format(exc))
            log_event(traceback.format_exc())

    def _present_ui():
        view = BikeTrainTransitView()
        try:
            view.present("fullscreen", hide_title_bar=True)
        except Exception as exc:
            msg = str(exc).casefold()
            if "widgets and shortcuts" in msg or (
                "present" in msg and "not available" in msg
            ):
                log_event("present blocked — handoff to full app: %s" % exc)
                from lib.shortcut_launcher import handoff_to_ui_app

                if handoff_to_ui_app():
                    return
            raise
        # Present first so the UI run loop is active, then kick off via ui.delay.
        # ui.delay timers registered before present() are unreliable on
        # Pythonista and may never fire (auto-refresh would be skipped).
        ui.delay(lambda: _kickoff_ui(view), 0.2)

    def _setup_launcher_background():
        try:
            print_shortcut_help()
        except KeyboardInterrupt:
            log_event("Deploy interrupted — UI still running")
        except Exception as exc:
            log_event("Launcher setup failed: %s" % exc)

    def main_ui():
        setup_debug(mode="full")
        start_debug_server(safe_mode=False)
        print("", flush=True)
        print("=== iOS Shortcut URL (run as main script) ===", flush=True)
        print(SHORTCUT_URL, flush=True)
        print("Home Screen: Shortcuts -> URL action + Open URLs action (two actions)", flush=True)
        threading.Thread(target=_setup_launcher_background, daemon=True).start()
        if _needs_ui_handoff():
            from lib.shortcut_launcher import handoff_to_ui_app

            log_event("Shortcuts context — opening full Pythonista app")
            if handoff_to_ui_app():
                return
            log_event("Handoff failed — trying deferred present")
            ui.delay(_present_ui, 1.5)
        else:
            _present_ui()

else:

    def main_ui():
        raise RuntimeError("UI mode requires Pythonista (ui module not available)")


def main_safe(port):
    from lib.file_logging import setup_safe_mode_logging
    from lib.lan_debug_server import run_lan_debug_server
    from lib.log_paths import LATEST_LOG, log_dir
    import asyncio

    setup_safe_mode_logging(port)
    print("Safe mode — LAN log server only (no Bike Train Transit UI)", flush=True)
    print("Log dir:", log_dir(), flush=True)
    print("Open", _lan_debug_url(), flush=True)
    print("Log", _lan_debug_url("/" + LATEST_LOG), flush=True)
    asyncio.run(run_lan_debug_server(LISTEN_HOST, port, safe_mode=True))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Print station counts to the terminal (for PC testing)",
    )
    parser.add_argument(
        "--safe",
        action="store_true",
        help="LAN log server only (no UI)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=LAN_DEBUG_PORT,
        help="LAN debug server port (default: %(default)s)",
    )
    parser.add_argument(
        "--inactive",
        metavar="SOURCE",
        action="append",
        choices=("citibike", "path", "subway", "hblr"),
        help="Disable a data source (repeatable; also set via BIKE_TRAIN_TRANSIT_INACTIVE)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    global LAN_DEBUG_PORT
    LAN_DEBUG_PORT = args.port
    if args.inactive:
        from lib.debug_flags import set_inactive

        set_inactive(*args.inactive)
    if args.safe:
        main_safe(args.port)
    elif args.cli or not HAS_UI:
        main_cli()
    else:
        main_ui()


if __name__ == "__main__":
    main()
