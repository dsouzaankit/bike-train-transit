# -*- coding: utf-8 -*-
"""Hudson-Bergen Light Rail (HBLR) southbound departures for the To JC tab.

Data source: NJ Transit Bus/Light-Rail API at pcsdata.njtransit.com, which
requires free developer credentials (username/password -> token). Without
credentials configured the boards come back empty and the To JC tab renders
exactly as before.

Offset logic mirrors the README PATH+subway rule: an HBLR train is only shown
if it departs at least `offset` minutes after the paired PATH station's earliest
NJ-bound train (PATH ETA + offset), i.e. enough time to ride PATH across the
river and walk to the light-rail platform.
"""

import datetime
import json
import os
import urllib.parse
import urllib.request

from . import clock

NJT_BASE = "https://pcsdata.njtransit.com"
NJT_AUTH_PATH = "/api/BUSDV2/authenticateUser"
NJT_DV_PATH = "/api/BUSDV2/getBusDV"
NJT_MODE = "HBLR"
NJT_TIMEOUT = 20

# Southbound HBLR termini we care about (West Side Avenue / 8th Street branches).
SOUTHBOUND_DESTINATIONS = (
    "west side",
    "8th st",
    "8th street",
    "bayonne",
)

# Each HBLR station is paired with a PATH NJ-bound board and a minute offset
# (PATH ride + walk) used to gate which departures are catchable.
LIGHT_RAIL_STATIONS = [
    {
        "label": "Newport",
        # NJT stop identifier — confirmed/adjusted against the live API.
        "njt_stop": "Newport",
        "path_pair": "Christopher St",
        "offset": 15,
        # Clock-face phase (min) for the offline schedule estimate.
        "phase": 0,
    },
    {
        "label": "Exchange Place",
        "njt_stop": "Exchange Place",
        "path_pair": "World Trade Center",
        "offset": 6,
        "phase": 3,
    },
]

LIGHT_RAIL_MAX_TRAINS = 3

# --- Offline schedule fallback ---------------------------------------------
# Approximate HBLR southbound (toward Bayonne: West Side Ave / 8th St) headways
# in minutes, as (start_min, end_min, headway) windows from local midnight.
# Used only when NJT realtime is unavailable (no creds / overnight / API error).
_SCHED_WEEKDAY = (
    (5 * 60, 6 * 60 + 30, 12),
    (6 * 60 + 30, 9 * 60 + 30, 6),
    (9 * 60 + 30, 15 * 60 + 30, 10),
    (15 * 60 + 30, 19 * 60, 6),
    (19 * 60, 22 * 60, 10),
    (22 * 60, 24 * 60, 15),
    (0, 60, 20),
)
_SCHED_SATURDAY = ((0, 90, 20), (5 * 60 + 30, 24 * 60, 12))
_SCHED_SUNDAY = ((0, 90, 20), (6 * 60, 24 * 60, 15))

_SOUTH_BRANCHES = ("8th St", "West Side Av")


def _load_credentials():
    """Return (username, password, token) from env or a gitignored creds file."""
    username = os.environ.get("NJTRANSIT_USERNAME")
    password = os.environ.get("NJTRANSIT_PASSWORD")
    token = os.environ.get("NJTRANSIT_TOKEN")
    if username and password:
        return username, password, token
    for name in ("njt_credentials.json", ".njt_credentials.json"):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return (
                data.get("username"),
                data.get("password"),
                data.get("token"),
            )
        except (OSError, ValueError):
            continue
    return username, password, token


def has_credentials():
    username, password, token = _load_credentials()
    return bool(token) or bool(username and password)


def _post_form(path, fields):
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        NJT_BASE + path,
        data=body,
        headers={
            "User-Agent": "bike-train-transit/2.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=NJT_TIMEOUT) as resp:
        raw = resp.read()
    if isinstance(raw, str):
        text = raw
    else:
        try:
            text = raw.decode("utf-8", "replace")
        except (TypeError, AttributeError):
            text = bytes(raw).decode("utf-8", "replace")
    return json.loads(text)


def _authenticate(username, password):
    payload = _post_form(NJT_AUTH_PATH, {"username": username, "password": password})
    if isinstance(payload, dict):
        return payload.get("UserToken") or payload.get("userToken") or payload.get("token")
    return None


def _parse_minutes(value):
    """NJT departures report minutes-to-arrival; normalize to int minutes."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("", "delayed", "cancelled"):
        return None
    if text in ("0", "due", "arriving", "now", "min"):
        return 0
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def _is_southbound_destination(name):
    text = (name or "").casefold()
    return any(token in text for token in SOUTHBOUND_DESTINATIONS)


def _fetch_station_departures(station, token):
    """Return a list of normalized HBLR train dicts for one station."""
    payload = _post_form(
        NJT_DV_PATH,
        {"token": token, "stop": station["njt_stop"], "mode": NJT_MODE},
    )
    items = []
    if isinstance(payload, dict):
        items = payload.get("DVTrain") or payload.get("departures") or payload.get("Predictions") or []
    elif isinstance(payload, list):
        items = payload
    trains = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        dest = (
            item.get("destination")
            or item.get("Destination")
            or item.get("headsign")
            or item.get("HEADSIGN")
            or "?"
        )
        if not _is_southbound_destination(dest):
            continue
        minutes = _parse_minutes(
            item.get("departuretime")
            or item.get("minutes")
            or item.get("SCHED_DEP_TIME")
            or item.get("eta")
        )
        eta = "Due" if minutes == 0 else ("%dm" % minutes if minutes is not None else "?")
        trains.append(
            {
                "line": None,
                "destination": _short_destination(dest),
                "minutes": minutes,
                "eta": eta,
                "status": item.get("status") or item.get("STATUS") or "ON_TIME",
            }
        )
    trains.sort(key=lambda t: t.get("minutes") if t.get("minutes") is not None else 9999)
    return trains


def _short_destination(name):
    text = (name or "").strip()
    low = text.casefold()
    if "west side" in low:
        return "West Side Av"
    if "8th" in low:
        return "8th St"
    if "bayonne" in low:
        return "8th St"
    return text or "?"


def _schedule_windows(now):
    wd = now.weekday()
    if wd <= 4:
        return _SCHED_WEEKDAY
    if wd == 5:
        return _SCHED_SATURDAY
    return _SCHED_SUNDAY


def _service_headway(now):
    """Return headway minutes for HBLR southbound at `now`, or None if no service."""
    minute_of_day = now.hour * 60 + now.minute
    for start, end, headway in _schedule_windows(now):
        if start <= minute_of_day < end:
            return headway
    return None


def offline_schedule_trains(station, now=None, count=12):
    """Estimated next southbound departures from a clock-face headway model.

    Generates a longer pool (default 12) so the PATH offset filter still has
    catchable departures beyond the offset window; callers cap the display.
    """
    now = now or clock.now()
    headway = _service_headway(now)
    if not headway:
        return []
    phase = station.get("phase", 0) % headway
    first = (phase - now.minute) % headway
    trains = []
    for i in range(max(1, count)):
        minutes = first + i * headway
        branch = _SOUTH_BRANCHES[(phase + i) % len(_SOUTH_BRANCHES)]
        trains.append(
            {
                "line": None,
                "destination": branch,
                "minutes": minutes,
                "eta": "Due" if minutes == 0 else "~%dm" % minutes,
                "status": "SCHED",
                "estimated": True,
            }
        )
    return trains


def get_light_rail_boards(fetch_json=None, now=None):
    """HBLR southbound boards per station; realtime when available, else schedule.

    `fetch_json` is accepted for signature parity with the other board loaders
    but unused (NJT needs POST auth, handled internally). Never raises.
    """
    username, password, token = _load_credentials()
    realtime = {}
    auth_error = None
    # When the clock is simulated, live data reflects real now, not the
    # pretended time — use the offline schedule instead.
    if not clock.is_simulated() and (token or (username and password)):
        try:
            if not token:
                token = _authenticate(username, password)
            if not token:
                raise RuntimeError("NJT auth returned no token")
            for station in LIGHT_RAIL_STATIONS:
                try:
                    realtime[station["label"]] = _fetch_station_departures(station, token)
                except Exception:
                    realtime[station["label"]] = None
        except Exception as exc:
            auth_error = str(exc)

    boards = []
    for station in LIGHT_RAIL_STATIONS:
        live = realtime.get(station["label"])
        if live:
            boards.append(
                {
                    "label": station["label"],
                    "trains": live[:LIGHT_RAIL_MAX_TRAINS],
                    "_raw_trains": live,
                    "error": None,
                    "by_line": True,
                }
            )
            continue
        sched = offline_schedule_trains(station, now)
        board = {
            "label": station["label"],
            "trains": sched[:LIGHT_RAIL_MAX_TRAINS],
            "_raw_trains": sched,
            "error": None,
            "by_line": True,
            "estimated": True,
            "note": "scheduled" if sched else "no service now",
        }
        if auth_error and not sched:
            board["note"] = "scheduled (NJT auth failed)"
        boards.append(board)
    return boards


def _earliest_path_minutes(path_board):
    earliest = None
    for train in (path_board or {}).get("trains") or []:
        minutes = train.get("minutes")
        if minutes is None:
            continue
        if earliest is None or minutes < earliest:
            earliest = minutes
    return earliest


def apply_path_lightrail_connections(light_rail_boards, path_nj_boards):
    """Keep HBLR trains departing >= paired PATH ETA + offset (To JC timing)."""
    path_by_label = {b.get("label"): b for b in path_nj_boards or []}
    spec_by_label = {st["label"]: st for st in LIGHT_RAIL_STATIONS}
    connected = []
    for board in light_rail_boards or []:
        spec = spec_by_label.get(board.get("label"))
        if spec is None:
            connected.append(board)
            continue
        path_min = _earliest_path_minutes(path_by_label.get(spec["path_pair"]))
        short_path = spec["path_pair"].replace(" PATH", "")
        new_board = dict(board)
        if path_min is None:
            new_board["note"] = "no %s PATH yet" % short_path
            connected.append(new_board)
            continue
        threshold = path_min + spec["offset"]
        source = board.get("_raw_trains") or board.get("trains") or []
        catchable = [
            train
            for train in source
            if train.get("minutes") is not None and train.get("minutes") >= threshold
        ]
        new_board["trains"] = catchable[:LIGHT_RAIL_MAX_TRAINS]
        note = "after %s PATH +%s" % (short_path, spec["offset"])
        if board.get("estimated"):
            note = "sched · " + note
        new_board["note"] = note
        if catchable:
            new_board["error"] = None
        connected.append(new_board)
    return connected
