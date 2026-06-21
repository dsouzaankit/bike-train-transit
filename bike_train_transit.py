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
SECTION_HEADER_HEIGHT = 26
SECTION_GAP = 10
TAB_BAR_HEIGHT = 34

LAN_DEBUG_ENABLED = True
LAN_DEBUG_PORT = 8765
LISTEN_HOST = "0.0.0.0"
SHORTCUT_SCRIPT = "RunBikeTrainTransit.py"
SHORTCUT_URL = "pythonista3://RunBikeTrainTransit.py?action=run"

GBFS_BASE = "https://gbfs.citibikenyc.com/gbfs/en"
_debug_started = False
TRANSIT_FETCH_TIMEOUT = 12
BIKE_FETCH_TIMEOUT = 10
BIKE_FETCH_RETRIES = 1
PATH_RAZZA_TIMEOUT = 5
PATH_RAZZA_RETRIES = 0

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


def _flush_logs():
    try:
        from lib.file_logging import flush_file_logs

        flush_file_logs()
    except Exception:
        pass


def print_shortcut_help():
    # Always print from main module — works even if lib/ on phone is stale.
    print("", flush=True)
    print("=== iOS Shortcut URL ===", flush=True)
    print(SHORTCUT_URL, flush=True)
    print("Launcher: On This iPhone -> %s" % SHORTCUT_SCRIPT, flush=True)
    try:
        from lib.shortcut_launcher import LAUNCHER_VERSION, launcher_help_lines
        from lib.local_deploy import local_app_dir

        lines = launcher_help_lines(_SCRIPT_DIR, install=False)
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
        "Bike Train Transit app started mode={} stations={}".format(mode, len(STATIONS))
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


def fetch_json(url, timeout=30, retries=2):
    last_error = None
    for attempt in range(max(1, retries + 1)):
        try:
            log_event("fetch_json open {} (attempt {})".format(url, attempt + 1))
            _flush_logs()
            req = urllib.request.Request(
                url, headers={"User-Agent": "bike-train-transit/2.0"}
            )
            opener = urllib.request.build_opener()
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
            log_event("fetch_json read {} bytes from {}".format(len(raw or b""), url))
            _flush_logs()
            if isinstance(raw, tuple):
                raw = raw[0] if raw else b""
            if isinstance(raw, str):
                text = raw
            else:
                text = raw.decode("utf-8", errors="replace")
            payload = json.loads(text)
            payload = _coerce_json_dict(payload, url)
            return payload
        except Exception as exc:
            last_error = exc
            log_event("fetch_json retry {} for {}: {}".format(attempt + 1, url, exc))
            _flush_logs()
    raise last_error


def _coerce_json_dict(payload, url):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, tuple):
        for item in payload:
            if isinstance(item, dict):
                log_event("fetch_json coerced tuple->dict for {}".format(url))
                return item
        raise ValueError("JSON tuple from %s had no dict element" % url)
    raise ValueError(
        "Expected JSON object from %s, got %s" % (url, type(payload).__name__)
    )


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


def fetch_bike_json(url):
    return fetch_json(url, timeout=BIKE_FETCH_TIMEOUT, retries=BIKE_FETCH_RETRIES)


_STATION_LOOKUP_CACHE = None


def station_lookup():
    global _STATION_LOOKUP_CACHE
    if _STATION_LOOKUP_CACHE is not None:
        return _STATION_LOOKUP_CACHE
    info = fetch_bike_json(GBFS_BASE + "/station_information.json")
    by_id = {}
    by_name = {}
    for s in _gbfs_stations(info, "station_information"):
        sid = str(s["station_id"])
        name = s["name"]
        by_id[sid] = name
        by_name[name.casefold()] = sid
        if "legacy_id" in s:
            by_id[str(s["legacy_id"])] = name
    _STATION_LOOKUP_CACHE = (by_id, by_name)
    return _STATION_LOOKUP_CACHE


def fetch_transit_json(url):
    return fetch_json(url, timeout=TRANSIT_FETCH_TIMEOUT)


def fetch_path_razza_json(url):
    return fetch_json(url, timeout=PATH_RAZZA_TIMEOUT, retries=PATH_RAZZA_RETRIES)


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


def build_snapshots(by_id, by_name, status_payload):
    status_by_id = {
        str(s["station_id"]): s for s in _gbfs_stations(status_payload, "station_status")
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


def get_snapshots():
    log_event("GBFS station_information...")
    _flush_logs()
    by_id, by_name = station_lookup()
    log_event("GBFS station_status...")
    _flush_logs()
    status = fetch_bike_json(GBFS_BASE + "/station_status.json")
    log_event("GBFS parsing status...")
    _flush_logs()
    return build_snapshots(by_id, by_name, status)


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


def _is_pythonista():
    import sys

    return "Pythonista" in sys.executable


def _fetch_transit_boards():
    """Fetch all transit boards in parallel; never raise."""
    if _is_pythonista():
        return _fetch_transit_boards_sequential()
    return _fetch_transit_boards_parallel()


def _fetch_transit_boards_sequential():
    path_bundle = {}
    subway_boards = []
    subway_to_jc_boards = []
    try:
        from lib.path_trains import get_all_path_boards

        path_bundle = get_all_path_boards(fetch_transit_json, fetch_path_razza_json)
    except Exception as exc:
        log_event("pathAll fetch failed: {}".format(exc))
        log_event(traceback.format_exc())
    try:
        subway_boards = get_subway_boards()
    except Exception as exc:
        log_event("subway fetch failed: {}".format(exc))
        log_event(traceback.format_exc())
    try:
        subway_to_jc_boards = get_subway_to_jc_boards()
    except Exception as exc:
        log_event("subwayToJc fetch failed: {}".format(exc))
        log_event(traceback.format_exc())
    path_boards = path_bundle.get("nyc") or []
    path_33rd_boards = path_bundle.get("33rd") or []
    path_nj_boards = path_bundle.get("nj") or []
    try:
        from lib.subway_trains import apply_path_subway_connections

        subway_boards = apply_path_subway_connections(subway_boards, path_33rd_boards)
    except Exception as exc:
        log_event("PATH+subway connection failed: {}".format(exc))
    return path_boards, path_33rd_boards, subway_boards, path_nj_boards, subway_to_jc_boards


def _fetch_transit_boards_parallel():
    from lib.parallel import run_parallel

    def _wrap(label, fn):
        try:
            return fn()
        except Exception as exc:
            log_event("{} fetch failed: {}".format(label, exc))
            log_event(traceback.format_exc())
            return [] if label != "pathAll" else {}

    def _fetch_path_all():
        from lib.path_trains import get_all_path_boards

        return get_all_path_boards(fetch_transit_json, fetch_path_razza_json)

    jobs = {
        "pathAll": _fetch_path_all,
        "subway": get_subway_boards,
        "subwayToJc": get_subway_to_jc_boards,
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
    try:
        from lib.subway_trains import apply_path_subway_connections

        subway_boards = apply_path_subway_connections(subway_boards, path_33rd_boards)
    except Exception as exc:
        log_event("PATH+subway connection failed: {}".format(exc))
    return path_boards, path_33rd_boards, subway_boards, path_nj_boards, subway_to_jc_boards


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
        path_boards, path_33rd_boards, subway_boards, path_nj_boards, subway_to_jc_boards = (
            _fetch_transit_boards()
        )
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
        from lib import app_state

        app_state.update_cli(
            snapshots,
            path_boards,
            subway_boards,
            path_33rd_boards,
            path_nj_boards,
            subway_to_jc_boards,
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

    class TransitCard(ui.View):
        def __init__(self, board, card_width, tag="NYC", empty_text="No trains"):
            super().__init__()
            self.background_color = COLORS["card"]
            self.corner_radius = 10
            self.border_width = 1
            self.border_color = "#2a3441"
            self.height = PATH_CARD_HEIGHT

            name = make_label(board["label"], font_size=13, bold=True)
            name.frame = (8, 6, card_width - 56, 18)

            tag_text = "~" if board.get("estimated") else tag
            tag_label = make_label(tag_text, font_size=10, bold=True, color=COLORS["accent"])
            tag_label.alignment = ui.ALIGN_RIGHT
            tag_label.frame = (card_width - 44, 6, 36, 14)

            trains = board.get("trains") or []
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

            for index, train in enumerate(trains[:2]):
                eta_size = 22 if index == 0 else 14
                dest_size = 13 if index == 0 else 11
                eta_color = COLORS["text"] if index == 0 else COLORS["muted"]
                dest_color = COLORS["text"] if index == 0 else COLORS["muted"]
                eta_text = str(train.get("eta") or "?")
                dest_text = str(train.get("destination") or "?")
                if train.get("status") == "DELAYED" or "delay" in eta_text.lower():
                    eta_color = COLORS["warn"]
                eta = make_label(
                    eta_text,
                    font_size=eta_size,
                    bold=(index == 0),
                    color=eta_color,
                )
                eta.frame = (8, y, 56, 24 if index == 0 else 18)
                line_x = 68
                line_val = train.get("line")
                if line_val not in (None, "", "?"):
                    line = make_label(
                        str(line_val),
                        font_size=dest_size,
                        bold=True,
                        color=COLORS["accent"],
                    )
                    line.frame = (line_x, y + (2 if index == 0 else 0), 18, 20)
                    self.add_subview(line)
                    line_x += 22
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

    class BikeTrainTransitView(ui.View):
        def __init__(self):
            super().__init__()
            self.background_color = COLORS["bg"]
            self.name = "Bike Train Transit"
            self._busy = False
            self._active_tab = "from_jc"
            self._cache = {"snapshots": []}
            self._ui_lock = threading.Lock()
            self._ui_queue = []
            self._ui_pump_active = False

            self.header = ui.View()
            self.header.background_color = COLORS["bg"]

            self.title_label = make_label("Bike Train Transit · %s" % REGION, font_size=24, bold=True)
            self.refresh_btn = ui.Button(title="Refresh")
            self.refresh_btn.background_color = COLORS["accent"]
            self.refresh_btn.tint_color = COLORS["text"]
            self.refresh_btn.corner_radius = 8
            self.refresh_btn.action = self.refresh_tapped

            self.status_label = make_label("Tap refresh to load", font_size=12, color=COLORS["muted"])

            self.tab_bar = ui.View()
            self.tab_bar.background_color = COLORS["bg"]
            self.tab_from_btn = ui.Button(title="From JC")
            self.tab_to_btn = ui.Button(title="To JC")
            self.tab_from_btn.corner_radius = 8
            self.tab_to_btn.corner_radius = 8
            self.tab_from_btn.action = self._tab_from_tapped
            self.tab_to_btn.action = self._tab_to_tapped
            self.tab_bar.add_subview(self.tab_from_btn)
            self.tab_bar.add_subview(self.tab_to_btn)

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
            active = self._active_tab == "from_jc"
            for btn, is_active in ((self.tab_from_btn, active), (self.tab_to_btn, not active)):
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

        def _tab_from_tapped(self, sender):
            self._set_tab("from_jc")

        def _tab_to_tapped(self, sender):
            self._set_tab("to_jc")

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
            ui.delay(lambda: self._poll_remote_control(), 1.0)

        def layout(self):
            safe_top = self.safe_area_insets.top if hasattr(self, "safe_area_insets") else 0
            width = self.width
            height = self.height
            header_h = 64 + safe_top
            tab_top = header_h + 2
            status_top = tab_top + TAB_BAR_HEIGHT + 2

            self.header.frame = (0, 0, width, header_h)
            self.title_label.frame = (16, safe_top + 8, width - 120, 28)
            self.refresh_btn.frame = (width - 96, safe_top + 8, 80, 30)
            self.tab_bar.frame = (0, tab_top, width, TAB_BAR_HEIGHT)
            tab_w = max((width - 40) // 2, 120)
            self.tab_from_btn.frame = (12, 0, tab_w, TAB_BAR_HEIGHT - 4)
            self.tab_to_btn.frame = (20 + tab_w, 0, tab_w, TAB_BAR_HEIGHT - 4)
            self.status_label.frame = (16, status_top, width - 32, 16)
            self.scroll.frame = (0, status_top + 20, width, height - status_top - 20)

        def _enqueue_ui(self, fn):
            with self._ui_lock:
                self._ui_queue.append(fn)

        def _run_ui_callbacks(self):
            import ui

            with self._ui_lock:
                batch = self._ui_queue[:]
                self._ui_queue.clear()
            for fn in batch:
                try:
                    fn()
                except Exception as exc:
                    log_event("UI callback failed: {}".format(exc))
                    log_event(traceback.format_exc())
            if self._busy or self._ui_queue:
                ui.delay(lambda: self._run_ui_callbacks(), 0.05)

        def _start_ui_pump(self):
            import ui

            if self._ui_pump_active:
                return
            self._ui_pump_active = True

            def pump():
                self._ui_pump_active = False
                self._run_ui_callbacks()

            ui.delay(pump, 0)

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
            try:
                from lib.file_logging import flush_file_logs

                flush_file_logs()
            except Exception:
                pass
            self._start_ui_pump()
            self._begin_bike_fetch()

        def _finish_refresh_error(self, error):
            from lib import app_state

            view = self
            try:
                view._busy = False
                app_state.set_busy(False)
                view.refresh_btn.enabled = True
                app_state.set_error(error)
                view.status_label.text = "Error: %s" % error
            except Exception as exc:
                log_event("UI finish failed: {}".format(exc))
                log_event(traceback.format_exc())

        def _begin_bike_fetch(self):
            import ui

            view = self

            @ui.in_background
            def fetch_info():
                try:
                    log_event("Fetching bikes...")
                    log_event("GBFS station_information...")
                    _flush_logs()
                    station_lookup()
                except Exception as exc:
                    log_event("Refresh failed: {}".format(exc))
                    log_event(traceback.format_exc())
                    view._enqueue_ui(lambda: view._finish_refresh_error(str(exc)))
                    return
                ui.delay(lambda: view._fetch_bike_status(), 0.05)

            fetch_info()

        def _fetch_bike_status(self):
            import ui

            view = self

            @ui.in_background
            def fetch_status():
                snapshots = None
                try:
                    log_event("GBFS station_status...")
                    _flush_logs()
                    status = fetch_bike_json(GBFS_BASE + "/station_status.json")
                    log_event("GBFS parsing status...")
                    _flush_logs()
                    by_id, by_name = station_lookup()
                    snapshots = build_snapshots(by_id, by_name, status)
                    log_event("Bikes fetched: {} stations".format(len(snapshots or [])))
                    _flush_logs()
                except Exception as exc:
                    log_event("Refresh failed: {}".format(exc))
                    log_event(traceback.format_exc())
                    view._enqueue_ui(lambda: view._finish_refresh_error(str(exc)))
                    return
                ui.delay(lambda: view._continue_refresh(snapshots), 0.05)

            fetch_status()

        def _continue_refresh(self, snapshots):
            import ui

            view = self

            def show_bikes():
                try:
                    log_event("UI bike paint start")
                    _flush_logs()
                    view.render_snapshots(
                        snapshots,
                        path_boards=None,
                        path_33rd_boards=None,
                        subway_boards=None,
                        path_nj_boards=None,
                        subway_to_jc_boards=None,
                        partial=True,
                    )
                    view.status_label.text = "Loading transit..."
                    log_event("UI bike paint done")
                    _flush_logs()
                except Exception as exc:
                    log_event("UI bike render failed: {}".format(exc))
                    log_event(traceback.format_exc())

            view._enqueue_ui(show_bikes)

            @ui.in_background
            def fetch_transit():
                path_boards = []
                path_33rd_boards = []
                subway_boards = []
                path_nj_boards = []
                subway_to_jc_boards = []
                try:
                    log_event("Transit fetch started")
                    (
                        path_boards,
                        path_33rd_boards,
                        subway_boards,
                        path_nj_boards,
                        subway_to_jc_boards,
                    ) = _fetch_transit_boards()
                    log_event("Transit fetch done")
                except Exception as exc:
                    log_event("Transit fetch failed: {}".format(exc))
                    log_event(traceback.format_exc())

                def finish():
                    from lib import app_state

                    try:
                        log_event("UI full paint start")
                        _flush_logs()
                        view._busy = False
                        app_state.set_busy(False)
                        view.refresh_btn.enabled = True
                        view.render_snapshots(
                            snapshots,
                            path_boards,
                            path_33rd_boards,
                            subway_boards,
                            path_nj_boards,
                            subway_to_jc_boards,
                        )
                        log_event("UI full paint done")
                        _flush_logs()
                    except Exception as exc:
                        view._busy = False
                        app_state.set_busy(False)
                        app_state.set_error(str(exc))
                        view.refresh_btn.enabled = True
                        view.status_label.text = "Error: %s" % exc
                        log_event("UI finish failed: {}".format(exc))
                        log_event(traceback.format_exc())

                view._enqueue_ui(finish)

            fetch_transit()

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
            for index, board in enumerate(boards):
                col = index % cols
                row = index // cols
                x = pad + col * (card_width + CARD_GAP)
                card_y = y + row * (PATH_CARD_HEIGHT + CARD_GAP)
                card = TransitCard(board, card_width, tag=tag, empty_text=empty_text)
                card.frame = (x, card_y, card_width, PATH_CARD_HEIGHT)
                self.scroll.add_subview(card)
            rows = (len(boards) + cols - 1) // cols if boards else 0
            if rows:
                y += rows * PATH_CARD_HEIGHT + max(0, rows - 1) * CARD_GAP
            return y + pad

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
            y = self._append_transit_section(
                y,
                pad,
                inner_w,
                card_width,
                "PATH → 33rd St",
                self._cache.get("path_33rd_boards"),
                tag="33",
                empty_text="No 33rd St trains",
            )
            y += SECTION_GAP
            y = self._append_transit_section(
                y,
                pad,
                inner_w,
                card_width,
                "Subway → North / Queens",
                self._cache.get("subway_boards"),
                tag="↑",
                empty_text="None after PATH",
            )
            return y

        def render_snapshots(
            self,
            snapshots,
            path_boards=None,
            path_33rd_boards=None,
            subway_boards=None,
            path_nj_boards=None,
            subway_to_jc_boards=None,
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
                log_event("Refresh OK: {} stations".format(len(snapshots or [])))
                try:
                    from lib.file_logging import mark_refresh_ok

                    mark_refresh_ok()
                except Exception:
                    pass
                app_state.update_refresh(
                    snapshots or self._cache.get("snapshots") or [],
                    path_boards,
                    subway_boards,
                    path_33rd_boards,
                    path_nj_boards,
                    subway_to_jc_boards,
                    active_tab=self._active_tab,
                    tagged_name_fn=tagged_name,
                )
            self._paint_active_tab(partial=partial)

        def _paint_active_tab(self, partial=False):
            import ui

            log_event(
                "UI paint tab={} partial={}".format(self._active_tab, partial)
            )
            for subview in list(self.scroll.subviews):
                self.scroll.remove_subview(subview)
            width = max(self.width - 16, 320)
            pad = 8
            inner_w = width - pad * 2
            card_width = (inner_w - CARD_GAP * (CARD_COLUMNS - 1)) // CARD_COLUMNS
            try:
                if self._active_tab == "to_jc":
                    y = self._paint_to_jc(pad, inner_w, card_width, partial=partial)
                else:
                    y = self._paint_from_jc(pad, inner_w, card_width, partial=partial)
                content_h = max(y, pad)
                self.scroll.content_size = (width, content_h)
                if content_h <= self.scroll.height:
                    self.scroll.content_offset = (0, 0)
                if not partial:
                    self.status_label.text = "Updated %s · %s" % (
                        datetime.now().strftime("%I:%M:%S %p"),
                        "To JC" if self._active_tab == "to_jc" else REGION,
                    )
            except Exception as exc:
                log_event("Paint failed: {}".format(exc))
                log_event(traceback.format_exc())
                self.status_label.text = "UI error: %s" % exc

        def _paint_from_jc(self, pad, inner_w, card_width, partial=False):
            snapshots = self._cache.get("snapshots") or []
            rows = (len(GRID_SLOTS) + CARD_COLUMNS - 1) // CARD_COLUMNS
            y = pad
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
            y = pad + rows * CARD_HEIGHT + max(0, rows - 1) * CARD_GAP + SECTION_GAP
            if partial:
                return y
            return self._append_from_jc_transit(y, pad, inner_w, card_width)

        def _paint_to_jc(self, pad, inner_w, card_width, partial=False):
            y = pad
            if partial:
                loading = make_label("Loading transit...", font_size=14, color=COLORS["muted"])
                loading.frame = (pad, y, inner_w, 24)
                self.scroll.add_subview(loading)
                return y + 32
            y = self._append_transit_section(
                y,
                pad,
                inner_w,
                card_width,
                "Subway → South Ferry",
                self._cache.get("subway_to_jc_boards"),
                tag="↓",
                empty_text="No downtown trains",
            )
            y += SECTION_GAP
            y = self._append_transit_section(
                y,
                pad,
                inner_w,
                card_width,
                "PATH → NJ",
                self._cache.get("path_nj_boards"),
                tag="NJ",
                empty_text="No NJ trains",
            )
            return y

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

    def _present_ui():
        view = BikeTrainTransitView()
        try:
            view.present("fullscreen")
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
        view.start_remote_poll()

    def _setup_launcher_background():
        try:
            print_shortcut_help()
        except KeyboardInterrupt:
            log_event("Deploy interrupted — UI still running")
        except Exception as exc:
            log_event("Launcher setup failed: %s" % exc)

    def main_ui():
        setup_debug(mode="full")
        try:
            from lib.shortcut_launcher import install_launcher

            install_launcher(_SCRIPT_DIR)
            log_event("Local deploy OK")
            _flush_logs()
        except Exception as exc:
            log_event("Local deploy failed: %s" % exc)
        start_debug_server(safe_mode=False)
        print("", flush=True)
        print("=== iOS Shortcut URL ===", flush=True)
        print(SHORTCUT_URL, flush=True)
        print("Launcher: On This iPhone -> %s" % SHORTCUT_SCRIPT, flush=True)
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
