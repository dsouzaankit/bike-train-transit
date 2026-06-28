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
"""

import argparse
import json
import os
import sys
import threading
import traceback
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
]
# Shorter labels for compact UI (same order as STATIONS)
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
]
# Snapshot indices (matches STATIONS order above):
#   0 Dixon Mills  1 Montgomery  |  2 Brunswick  3 Monmouth  4 Jersey & 6th
#   5 Newport PATH  6 Washington  |  7 City Hall  8 Grove St PATH
#
# Group 1 — 6th St (2x2, empty cell beside Jersey)
# Group 2 — Newport PATH, Washington St
# Group 3 — Dixon Mills, Montgomery St
GRID_GROUPS = [
    [(0, 1)],              # Group 3
    [(2, 3), (4, None)],   # Group 1
    [(5, 6)],              # Group 2
    [(7, 8)],              # City Hall, Grove St PATH
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
SECTION_HEADER_HEIGHT = 26
SECTION_GAP = 10
TAB_BAR_HEIGHT = 34
TOP_CONTENT_INSET = 43  # ~1.5 cm below screen top so chrome clears the iOS status bar / notch

LAN_DEBUG_ENABLED = True
LAN_DEBUG_PORT = 8765
LISTEN_HOST = "0.0.0.0"
SHORTCUT_URL = "pythonista3://bike_train_transit/bike_train_transit.py?action=run"

GBFS_BASE = "https://gbfs.citibikenyc.com/gbfs/en"
_debug_started = False
TRANSIT_FETCH_TIMEOUT = 12
BUILD_TAG = "transit-tunnels-v1"

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
    log_banner(
        "Bike Train Transit app started mode={} stations={} build={}".format(
            mode, len(STATIONS), BUILD_TAG
        )
    )


def _local_ip():
    from lib.net_util import get_lan_debug_ip

    return get_lan_debug_ip(LISTEN_HOST)


def debug_status():
    from lib import app_state

    return app_state.snapshot()


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
    ip = _local_ip()
    banner = "LAN debug: http://{}:{}/".format(ip, LAN_DEBUG_PORT)
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


def fetch_json(url, timeout=30, retries=2):
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
            return payload
        except Exception as exc:
            last_error = exc
            log_event("fetch_json retry {} for {}: {}".format(attempt + 1, url, exc))
    raise last_error


def _gbfs_stations(payload, label="GBFS"):
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
    return stations


def station_lookup():
    info = fetch_json(GBFS_BASE + "/station_information.json")
    by_id = {}
    by_name = {}
    for s in _gbfs_stations(info, "station_information"):
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


def get_light_rail_boards():
    from lib.light_rail import get_light_rail_boards as _get_light_rail_boards

    return _get_light_rail_boards(fetch_transit_json)


def _fetch_transit_boards():
    """Fetch all transit boards in parallel; never raise."""
    from lib.parallel import run_parallel

    def _wrap(label, fn):
        log_event("step: transit {} start".format(label))
        try:
            result = fn()
            log_event("step: transit {} ok".format(label))
            return result
        except Exception as exc:
            log_event("{} fetch failed: {}".format(label, exc))
            log_event(traceback.format_exc())
            return [] if label != "pathAll" else {}

    def _fetch_path_all():
        from lib.path_trains import get_all_path_boards

        return get_all_path_boards(fetch_transit_json)

    jobs = {
        "pathAll": _fetch_path_all,
        "subway": get_subway_boards,
        "subwayToJc": get_subway_to_jc_boards,
        "tunnels": lambda: __import__("lib.tunnel_crossings", fromlist=["get_tunnel_boards"]).get_tunnel_boards(
            fetch_transit_payload
        ),
        "lightRail": get_light_rail_boards,
    }
    results = run_parallel(
        {key: (lambda k=key, f=fn: _wrap(k, f)) for key, fn in jobs.items()},
        timeout=TRANSIT_FETCH_TIMEOUT * 3,
    )
    path_bundle = results.get("pathAll") or {}
    path_boards = path_bundle.get("nyc") or []
    path_33rd_boards = path_bundle.get("33rd") or []
    path_nj_boards = path_bundle.get("nj") or []
    subway_boards = results.get("subway") or []
    subway_to_jc_boards = results.get("subwayToJc") or []
    tunnel_boards = results.get("tunnels") or []
    light_rail_boards = results.get("lightRail") or []
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
    if light_rail_boards:
        try:
            from lib.light_rail import apply_path_lightrail_connections

            light_rail_boards = apply_path_lightrail_connections(
                light_rail_boards, path_nj_boards
            )
            log_event("step: HBLR connections done ({})".format(len(light_rail_boards)))
        except Exception as exc:
            log_event("PATH+HBLR connection failed: {}".format(exc))
            log_event(traceback.format_exc())
    log_event("step: transit boards assembled")
    return (
        path_boards,
        path_33rd_boards,
        subway_boards,
        path_nj_boards,
        subway_to_jc_boards,
        tunnel_boards,
        light_rail_boards,
    )


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
            light_rail_boards,
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
        print_subway_boards(subway_to_jc_boards, title="Subway To JC")
        print("")
        for board in light_rail_boards or []:
            trains = ", ".join(
                "%s %s" % (t.get("eta"), t.get("destination")) for t in board.get("trains") or []
            ) or (board.get("error") or "(none)")
            print("HBLR %s: %s" % (board.get("label"), trains))
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

    def make_label(text, font_size=16, bold=False, color=COLORS["text"], align=ui.ALIGN_LEFT):
        label = ui.Label()
        label.text = text
        label.font = ("<system-bold>" if bold else "<system>", font_size)
        label.text_color = color
        label.alignment = align
        label.number_of_lines = 0
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

            name = make_label(snapshot["label"], font_size=13, bold=True)
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

    def transit_card_height(board):
        if board.get("tunnel_card"):
            rows = len(board.get("trains") or []) or 1
            note_h = 0
            header_h = 30
            if board.get("error") and not board.get("trains"):
                return header_h + 24
            return header_h + rows * TUNNEL_ROW_HEIGHT + 10

        note_h = 12 if board.get("note") else 0
        header_h = 28 + note_h
        if board.get("error"):
            return max(PATH_CARD_HEIGHT, header_h + 20)
        trains = board.get("trains") or []
        if not trains:
            return max(PATH_CARD_HEIGHT, header_h + 20)
        if board.get("by_line"):
            return header_h + len(trains) * TRANSIT_LINE_ROW_HEIGHT + 10
        return header_h + min(len(trains), 2) * 26 + 8

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
        def __init__(self, board, card_width, tag="NYC", empty_text="No trains"):
            super().__init__()
            self.background_color = COLORS["card"]
            self.corner_radius = 10
            self.border_width = 1
            self.border_color = "#2a3441"
            self.height = transit_card_height(board)

            name = make_label(board["label"], font_size=13, bold=True)
            name.frame = (8, 6, card_width - 56, 18)

            tag_text = "~" if board.get("estimated") else tag
            tag_label = make_label(tag_text, font_size=10, bold=True, color=COLORS["accent"])
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
                note = make_label(board["note"], font_size=10, color=COLORS["muted"])
                note.frame = (8, 24, card_width - 16, 12)
                self.add_subview(note)
                y = 36
            if error:
                line = make_label("Unavailable", font_size=12, color=COLORS["bad"])
                line.frame = (8, y, card_width - 16, 16)
                self.add_subview(line)
                return
            if not trains:
                line = make_label(empty_text, font_size=12, color=COLORS["muted"])
                line.frame = (8, y, card_width - 16, 16)
                self.add_subview(line)
                return

            if board.get("by_line"):
                for train in trains:
                    eta_text = format_train_eta(train)
                    dest_text = str(train.get("destination") or "?")
                    eta_color = COLORS["text"]
                    if train.get("status") == "DELAYED" or "delay" in eta_text.lower():
                        eta_color = COLORS["warn"]
                    eta = make_label(eta_text, font_size=14, bold=True, color=eta_color)
                    eta.frame = (8, y, ETA_COLUMN_WIDTH - 8, 20)
                    line_x = 8 + ETA_COLUMN_WIDTH - 4
                    line_val = train.get("line")
                    if line_val not in (None, "", "?"):
                        line_x += _add_line_badge(self, line_val, line_x, y + 1)
                    dest = make_label(dest_text, font_size=11, color=COLORS["muted"])
                    dest.frame = (line_x, y + 2, card_width - line_x - 8, 18)
                    self.add_subview(eta)
                    self.add_subview(dest)
                    y += TRANSIT_LINE_ROW_HEIGHT
                return

            for index, train in enumerate(trains[:2]):
                eta_size = 22 if index == 0 else 14
                dest_size = 13 if index == 0 else 11
                eta_color = COLORS["text"] if index == 0 else COLORS["muted"]
                dest_color = COLORS["text"] if index == 0 else COLORS["muted"]
                eta_text = format_train_eta(train)
                dest_text = str(train.get("destination") or "?")
                if train.get("status") == "DELAYED" or "delay" in eta_text.lower():
                    eta_color = COLORS["warn"]
                eta = make_label(
                    eta_text,
                    font_size=eta_size,
                    bold=(index == 0),
                    color=eta_color,
                )
                eta.frame = (8, y, ETA_COLUMN_WIDTH, 24 if index == 0 else 18)
                line_x = 8 + ETA_COLUMN_WIDTH
                line_val = train.get("line")
                if line_val not in (None, "", "?"):
                    line_x += _add_line_badge(self, line_val, line_x, y + (2 if index == 0 else 0))
                dest = make_label(
                    dest_text,
                    font_size=dest_size,
                    bold=(index == 0),
                    color=dest_color,
                )
                dest.frame = (line_x, y + (2 if index == 0 else 0), card_width - line_x - 8, 20)
                self.add_subview(eta)
                self.add_subview(dest)
                y += 28 if index == 0 else 24

    class TunnelCard(ui.View):
        def __init__(self, board, card_width):
            super().__init__()
            self.background_color = COLORS["card"]
            self.corner_radius = 10
            self.border_width = 1
            self.border_color = "#2a3441"
            self.height = transit_card_height(board)

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

    class BikeTrainTransitView(ui.View):
        def __init__(self):
            super().__init__()
            self.background_color = COLORS["bg"]
            self.name = APP_TITLE
            self._busy = False
            self._active_tab = "from_jc"
            self._cache = {"snapshots": []}

            self.header = ui.View()
            self.header.background_color = COLORS["bg"]

            self.title_label = make_label(APP_TITLE, font_size=24, bold=True)
            self.refresh_btn = ui.Button(title="Refresh")
            self.refresh_btn.background_color = COLORS["accent"]
            self.refresh_btn.tint_color = COLORS["text"]
            self.refresh_btn.corner_radius = 8
            self.refresh_btn.action = self.refresh_tapped

            self.status_label = make_label("", font_size=12, color=COLORS["muted"])

            self.tab_bar = ui.View()
            self.tab_bar.background_color = COLORS["bg"]
            self.tab_cbike_btn = ui.Button(title="Cbike JC")
            self.tab_from_btn = ui.Button(title="From JC")
            self.tab_to_btn = ui.Button(title="To JC")
            self.tab_tunnels_btn = ui.Button(title="Tunnels")
            for btn in (self.tab_cbike_btn, self.tab_from_btn, self.tab_to_btn, self.tab_tunnels_btn):
                btn.corner_radius = 8
            self.tab_cbike_btn.action = self._tab_cbike_tapped
            self.tab_from_btn.action = self._tab_from_tapped
            self.tab_to_btn.action = self._tab_to_tapped
            self.tab_tunnels_btn.action = self._tab_tunnels_tapped
            self.tab_bar.add_subview(self.tab_cbike_btn)
            self.tab_bar.add_subview(self.tab_from_btn)
            self.tab_bar.add_subview(self.tab_to_btn)
            self.tab_bar.add_subview(self.tab_tunnels_btn)

            self.scroll = ui.ScrollView()
            self.scroll.background_color = COLORS["bg"]
            self.scroll.shows_vertical_scroll_indicator = False

            self.header.add_subview(self.title_label)
            self.header.add_subview(self.refresh_btn)
            self.add_subview(self.header)
            self.add_subview(self.tab_bar)
            self.add_subview(self.status_label)
            self.add_subview(self.scroll)
            self._style_tabs()

        def start_remote_poll(self):
            self._poll_remote_control()

        def _style_tabs(self):
            for tab, btn in (
                ("cbike_jc", self.tab_cbike_btn),
                ("from_jc", self.tab_from_btn),
                ("to_jc", self.tab_to_btn),
                ("tunnels", self.tab_tunnels_btn),
            ):
                is_active = self._active_tab == tab
                btn.background_color = COLORS["accent"] if is_active else "#2a3441"
                btn.tint_color = COLORS["text"]
                btn.font = ("<system-bold>", 14) if is_active else ("<system>", 14)

        def _set_tab(self, tab):
            if self._active_tab == tab:
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

        def _tab_cbike_tapped(self, sender):
            self._set_tab("cbike_jc")

        def _tab_from_tapped(self, sender):
            self._set_tab("from_jc")

        def _tab_to_tapped(self, sender):
            self._set_tab("to_jc")

        def _tab_tunnels_tapped(self, sender):
            self._set_tab("tunnels")

        def _poll_remote_control(self):
            import ui

            try:
                from lib.app_control import clear_control, is_refresh_requested

                if is_refresh_requested():
                    clear_control()
                    log_event("LAN refresh requested")
                    self.refresh()
            except Exception:
                pass
            ui.delay(self._poll_remote_control, 1.0)

        def layout(self):
            top = TOP_CONTENT_INSET
            width = self.width
            height = self.height
            header_h = 64 + top
            tab_top = header_h + 2
            status_top = tab_top + TAB_BAR_HEIGHT + 2

            self.header.frame = (0, 0, width, header_h)
            self.title_label.frame = (16, top + 8, width - 120, 28)
            self.refresh_btn.frame = (width - 96, top + 8, 80, 30)
            self.tab_bar.frame = (0, tab_top, width, TAB_BAR_HEIGHT)
            tab_gap = 4
            tab_side = 6
            tab_count = 4
            tab_w = max((width - tab_side * 2 - tab_gap * (tab_count - 1)) // tab_count, 72)
            self.tab_cbike_btn.frame = (tab_side, 0, tab_w, TAB_BAR_HEIGHT - 4)
            self.tab_from_btn.frame = (tab_side + (tab_w + tab_gap), 0, tab_w, TAB_BAR_HEIGHT - 4)
            self.tab_to_btn.frame = (tab_side + 2 * (tab_w + tab_gap), 0, tab_w, TAB_BAR_HEIGHT - 4)
            self.tab_tunnels_btn.frame = (
                tab_side + 3 * (tab_w + tab_gap),
                0,
                tab_w,
                TAB_BAR_HEIGHT - 4,
            )
            self.status_label.frame = (16, status_top, width - 32, 16)
            self.scroll.frame = (0, status_top + 20, width, height - status_top - 20)

        def refresh_tapped(self, sender):
            self.refresh()

        def refresh(self):
            if self._busy:
                return
            from lib import app_state

            self._busy = True
            app_state.set_busy(True)
            self.refresh_btn.enabled = False
            self.status_label.text = "Updating..."
            log_event("Refresh started")

            @ui.in_background
            def work():
                error = None
                snapshots = None
                path_boards = []
                path_33rd_boards = []
                subway_boards = []
                path_nj_boards = []
                subway_to_jc_boards = []
                tunnel_boards = []
                light_rail_boards = []

                try:
                    log_event("step: fetch bikes")
                    snapshots = get_snapshots()
                    log_event("step: bikes ok ({})".format(len(snapshots or [])))
                except Exception as exc:
                    error = str(exc)
                    log_event("Refresh failed: {}".format(error))
                    log_event(traceback.format_exc())

                if error:

                    def finish_error():
                        import ui
                        from lib import app_state

                        try:
                            self._busy = False
                            app_state.set_busy(False)
                            self.refresh_btn.enabled = True
                            app_state.set_error(error)
                            self.status_label.text = "Error: %s" % error
                        except Exception as exc:
                            log_event("UI finish failed: {}".format(exc))
                            log_event(traceback.format_exc())

                    ui.delay(finish_error, 0)
                    return

                def show_bikes():
                    import ui

                    try:
                        log_event("step: paint bikes")
                        self.render_snapshots(
                            snapshots,
                            path_boards=None,
                            path_33rd_boards=None,
                            subway_boards=None,
                            path_nj_boards=None,
                            subway_to_jc_boards=None,
                            tunnel_boards=None,
                            partial=True,
                        )
                        self.status_label.text = "Loading transit..."
                        log_event("step: bikes painted")
                    except Exception as exc:
                        log_event("UI bike render failed: {}".format(exc))
                        log_event(traceback.format_exc())

                ui.delay(show_bikes, 0)

                try:
                    log_event("step: fetch transit")
                    (
                        path_boards,
                        path_33rd_boards,
                        subway_boards,
                        path_nj_boards,
                        subway_to_jc_boards,
                        tunnel_boards,
                        light_rail_boards,
                    ) = _fetch_transit_boards()
                    log_event("step: transit ok")
                except Exception as exc:
                    log_event("Transit fetch failed: {}".format(exc))
                    log_event(traceback.format_exc())

                def finish():
                    import ui
                    from lib import app_state

                    try:
                        self._busy = False
                        app_state.set_busy(False)
                        self.refresh_btn.enabled = True
                        log_event("step: finish render start")
                        self.render_snapshots(
                            snapshots,
                            path_boards,
                            path_33rd_boards,
                            subway_boards,
                            path_nj_boards,
                            subway_to_jc_boards,
                            tunnel_boards,
                            light_rail_boards,
                        )
                        log_event("step: finish render done")
                    except Exception as exc:
                        self._busy = False
                        app_state.set_busy(False)
                        app_state.set_error(str(exc))
                        self.refresh_btn.enabled = True
                        self.status_label.text = "Error: %s" % exc
                        log_event("UI finish failed: {}".format(exc))
                        log_event(traceback.format_exc())

                log_event("step: scheduling finish render")
                ui.delay(finish, 0)

            work()

        def _log_transit_boards(self, prefix, boards):
            if not boards:
                return
            for board in boards:
                if board.get("error"):
                    log_event("{} {} unavailable: {}".format(prefix, board["label"], board["error"]))
                    continue
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
                    row_heights.append(transit_card_height(board))
                    row_boards.append([])
                else:
                    row_heights[-1] = max(row_heights[-1], transit_card_height(board))
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

        def _append_tile_row(self, y, pad, inner_w, card_width, tiles):
            """tiles: list of (board, tag, empty_text). Two columns per row."""
            if not tiles:
                return y
            cols = CARD_COLUMNS
            row_groups = []
            row_heights = []
            for index, tile in enumerate(tiles):
                board = tile[0]
                col = index % cols
                if col == 0:
                    row_groups.append([])
                    row_heights.append(transit_card_height(board))
                else:
                    row_heights[-1] = max(row_heights[-1], transit_card_height(board))
                row_groups[-1].append((index, tile))

            row_y = y
            for row_index, group in enumerate(row_groups):
                row_h = row_heights[row_index]
                for index, (board, tag, empty_text) in group:
                    col = index % cols
                    x = pad + col * (card_width + CARD_GAP)
                    card = TransitCard(board, card_width, tag=tag, empty_text=empty_text)
                    card.frame = (x, row_y, card_width, row_h)
                    self.scroll.add_subview(card)
                row_y += row_h + CARD_GAP
            return row_y

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
                    (self._pick_board(path33, "Christopher St"), "33", "No 33rd St"),
                    (self._pick_board(subway, "Christopher St", by_line=True), "↑", "None after PATH"),
                ],
                [
                    (self._pick_board(path33, "9th St"), "33", "No 33rd St"),
                    (self._pick_board(subway, "West 4 St", by_line=True), "↑", "None after PATH"),
                ],
                [
                    (self._pick_board(path33, "14 St PATH"), "33", "No 33rd St"),
                    (self._pick_board(subway, "6 Av", by_line=True), "↑", "None after PATH"),
                    (self._pick_board(subway, "14 St - Union Sq", by_line=True), "↑", "None after PATH"),
                ],
                [
                    (self._pick_board(subway, "51 St", by_line=True), "↑", "No uptown trains"),
                    (self._pick_board(subway, "50 St", by_line=True), "↑", "No uptown trains"),
                ],
                [
                    (self._pick_board(subway, "Bleecker St", by_line=True), "↓", "No downtown trains"),
                ],
            )
            for group in groups:
                y = self._append_tile_row(y, pad, inner_w, card_width, group)
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
            light_rail_boards=None,
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
                self._cache["light_rail_boards"] = light_rail_boards
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
                self._log_transit_boards("HBLR", light_rail_boards)
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
                        "tunnels": "Tunnels",
                    }
                    self.status_label.text = "Updated %s · %s" % (
                        datetime.now().strftime("%I:%M:%S %p"),
                        tab_labels.get(self._active_tab, REGION),
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
            y = pad
            if partial:
                loading = make_label("Loading transit...", font_size=14, color=COLORS["muted"])
                loading.frame = (pad, y, inner_w, 24)
                self.scroll.add_subview(loading)
                return y + 32
            return self._append_from_jc_transit(y, pad, inner_w, card_width)

        def _paint_to_jc(self, pad, inner_w, card_width, partial=False):
            y = pad
            if partial:
                loading = make_label("Loading transit...", font_size=14, color=COLORS["muted"])
                loading.frame = (pad, y, inner_w, 24)
                self.scroll.add_subview(loading)
                return y + 32

            subway_boards = self._cache.get("subway_to_jc_boards") or []
            path_nj_boards = self._cache.get("path_nj_boards") or []
            wtc_path = self._pick_board(path_nj_boards, "World Trade Center")
            path_nj_rest = [
                board for board in path_nj_boards if board.get("label") != "World Trade Center"
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

            light_rail_boards = self._cache.get("light_rail_boards") or []
            if light_rail_boards:
                y += SECTION_GAP
                y = self._append_transit_section(
                    y,
                    pad,
                    inner_w,
                    card_width,
                    "HBLR → Bayonne",
                    light_rail_boards,
                    tag="↓",
                    empty_text="No HBLR after PATH",
                )
            return y

        def _paint_tunnels(self, pad, inner_w, card_width, partial=False):
            y = pad
            if partial:
                loading = make_label("Loading tunnels...", font_size=14, color=COLORS["muted"])
                loading.frame = (pad, y, inner_w, 24)
                self.scroll.add_subview(loading)
                return y + 32
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
            log_event("kickoff: poll + first refresh")
            view.start_remote_poll()
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
    import asyncio

    setup_safe_mode_logging(port)
    print("Safe mode — LAN log server only (no Bike Train Transit UI)", flush=True)
    from lib.log_paths import log_dir

    print("Log dir:", log_dir(), flush=True)
    print("Open http://<phone-ip>:{}/".format(port), flush=True)
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
    return parser.parse_args()


def main():
    args = parse_args()
    global LAN_DEBUG_PORT
    LAN_DEBUG_PORT = args.port
    if args.safe:
        main_safe(args.port)
    elif args.cli or not HAS_UI:
        main_cli()
    else:
        main_ui()


if __name__ == "__main__":
    main()
