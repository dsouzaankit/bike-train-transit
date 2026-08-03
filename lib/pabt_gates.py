# -*- coding: utf-8 -*-
"""PABT gate schedules from portauthoritygate.com (119 / 123 / 126).

Hardcoded windows ship in ``pabt_gates_data.json``. A user Refresh scrapes
https://portauthoritygate.com/{route} and rewrites that snapshot.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import urllib.request
from html import unescape
from typing import Callable

# Same routes as HOB↔MT PABT dep board.
PABT_GATE_ROUTES = ("119", "123", "126")
PABT_GATES_BASE_URL = "https://portauthoritygate.com"
SECTION_CURRENT = "Gates now"
PABT_GATES_SECTION_TITLES = (SECTION_CURRENT,)

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "pabt_gates_data.json"
)
_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

_TIME_RE = re.compile(
    r"(\d{1,2}:\d{2}\s*[AP]M)\s*[-–—]\s*(\d{1,2}:\d{2}\s*[AP]M)",
    re.I,
)
_GATE_RE = re.compile(r"^Gate\s+(\d+)\s*$", re.I)
_DOOR_RE = re.compile(r"^Door\s+(\d+)\s*$", re.I)
_NOTE_EXCEPT_L = re.compile(r'except\s+"?l"?\s+trips', re.I)
_NOTE_L_ONLY = re.compile(r'"?l"?\s+trips\s+only', re.I)
_NOTE_ALL = re.compile(r"^all\s+trips$", re.I)

FetchHtml = Callable[[str], str]


# ---------------------------------------------------------------------------
# Clock helpers
# ---------------------------------------------------------------------------


def parse_clock_minutes(text: str) -> int:
    """``6:00 AM`` / ``10:01 PM`` → minutes since midnight (0–1439)."""
    raw = str(text or "").strip().upper().replace(".", "")
    match = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", raw)
    if not match:
        raise ValueError("bad clock: %r" % text)
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = match.group(3)
    if hour == 12:
        hour = 0
    if ampm == "PM":
        hour += 12
    return hour * 60 + minute


def format_clock_minutes(minutes: int) -> str:
    minutes = int(minutes) % (24 * 60)
    hour24, minute = divmod(minutes, 60)
    ampm = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12 or 12
    return "%d:%02d %s" % (hour12, minute, ampm)


def window_contains(start_min: int, end_min: int, now_min: int) -> bool:
    """Inclusive window; supports overnight wrap (e.g. 10:01 PM–1:00 AM)."""
    start_min = int(start_min) % (24 * 60)
    end_min = int(end_min) % (24 * 60)
    now_min = int(now_min) % (24 * 60)
    if start_min <= end_min:
        return start_min <= now_min <= end_min
    return now_min >= start_min or now_min <= end_min


def _normalize_note(note: str | None) -> str | None:
    if not note:
        return None
    text = str(note).strip()
    if _NOTE_EXCEPT_L.search(text):
        return "except_l"
    if _NOTE_L_ONLY.search(text):
        return "l_only"
    if _NOTE_ALL.search(text):
        return "all"
    return text


def is_126_l_trip(destination: str | None) -> bool:
    """Heuristic: 126 Limited / ``L`` trips in headsign."""
    text = str(destination or "")
    if re.search(r"\bL\b", text):
        return True
    low = text.casefold()
    return "limited" in low or '"l"' in low or " l " in " %s " % low


# ---------------------------------------------------------------------------
# HTML scrape / parse
# ---------------------------------------------------------------------------


def html_to_lines(html: str) -> list[str]:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html or "", flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = unescape(text)
    lines: list[str] = []
    seen_blank = False
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            if not seen_blank:
                lines.append("")
                seen_blank = True
            continue
        seen_blank = False
        lines.append(line)
    return lines


def parse_route_html(html: str, route: str) -> list[dict]:
    """Parse portauthoritygate.com route page into gate windows."""
    lines = html_to_lines(html)
    windows: list[dict] = []
    pending_note: str | None = None
    pending_start: int | None = None
    pending_end: int | None = None
    pending_gate: str | None = None
    pending_door: str | None = None

    def flush() -> None:
        nonlocal pending_note, pending_start, pending_end, pending_gate, pending_door
        if pending_start is None or pending_end is None or not pending_gate:
            pending_note = None
            pending_start = None
            pending_end = None
            pending_gate = None
            pending_door = None
            return
        entry = {
            "start_min": pending_start,
            "end_min": pending_end,
            "start": format_clock_minutes(pending_start),
            "end": format_clock_minutes(pending_end),
            "gate": str(pending_gate),
            "door": pending_door,
            "note": _normalize_note(pending_note),
        }
        # Deduplicate Framer double-render.
        if not windows or windows[-1] != entry:
            windows.append(entry)
        pending_note = None
        pending_start = None
        pending_end = None
        pending_gate = None
        pending_door = None

    for line in lines:
        if not line:
            continue
        note_norm = _normalize_note(line)
        if note_norm in ("except_l", "l_only", "all") or (
            note_norm and note_norm == line.strip() and "trip" in line.casefold()
        ):
            # New note starts a new window after previous gate.
            if pending_gate:
                flush()
            pending_note = note_norm if note_norm in ("except_l", "l_only", "all") else line
            continue
        time_match = _TIME_RE.fullmatch(line)
        if time_match:
            if pending_gate:
                flush()
            pending_start = parse_clock_minutes(time_match.group(1))
            pending_end = parse_clock_minutes(time_match.group(2))
            continue
        gate_match = _GATE_RE.fullmatch(line)
        if gate_match:
            if pending_gate and pending_gate != gate_match.group(1):
                flush()
            pending_gate = gate_match.group(1)
            continue
        door_match = _DOOR_RE.fullmatch(line)
        if door_match:
            pending_door = door_match.group(1)
            flush()
            continue
    flush()
    if not windows:
        raise ValueError("no gate windows for route %s" % route)
    return windows


def default_fetch_html(url: str, *, timeout: float = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def scrape_route_schedule(
    route: str, *, fetch_html: FetchHtml | None = None
) -> list[dict]:
    fetch = fetch_html or default_fetch_html
    url = "%s/%s" % (PABT_GATES_BASE_URL, route)
    return parse_route_html(fetch(url), route)


def scrape_all_schedules(
    *, fetch_html: FetchHtml | None = None, routes: tuple[str, ...] = PABT_GATE_ROUTES
) -> dict:
    """Scrape all routes; return data dict ready to persist."""
    schedules: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}
    for route in routes:
        try:
            schedules[route] = scrape_route_schedule(route, fetch_html=fetch_html)
        except Exception as exc:
            errors[route] = str(exc)
    payload = {
        "source": PABT_GATES_BASE_URL,
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "routes": schedules,
        "errors": errors,
    }
    if not schedules:
        raise RuntimeError("PABT gate scrape failed: %s" % (errors or "empty"))
    return payload


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

# Built-in fallback if JSON missing (from portauthoritygate.com 2026-08-03).
_BUILTIN_ROUTES: dict[str, list[dict]] = {
    "119": [
        {
            "start_min": 6 * 60,
            "end_min": 22 * 60,
            "start": "6:00 AM",
            "end": "10:00 PM",
            "gate": "210",
            "door": "1",
            "note": None,
        },
        {
            "start_min": 22 * 60 + 1,
            "end_min": 1 * 60,
            "start": "10:01 PM",
            "end": "1:00 AM",
            "gate": "322",
            "door": None,
            "note": None,
        },
        {
            "start_min": 1 * 60 + 1,
            "end_min": 5 * 60 + 59,
            "start": "1:01 AM",
            "end": "5:59 AM",
            "gate": "80",
            "door": None,
            "note": None,
        },
    ],
    "123": [
        {
            "start_min": 6 * 60,
            "end_min": 22 * 60,
            "start": "6:00 AM",
            "end": "10:00 PM",
            "gate": "211",
            "door": "1",
            "note": None,
        },
        {
            "start_min": 22 * 60 + 1,
            "end_min": 1 * 60,
            "start": "10:01 PM",
            "end": "1:00 AM",
            "gate": "303",
            "door": None,
            "note": None,
        },
        {
            "start_min": 1 * 60 + 1,
            "end_min": 5 * 60 + 59,
            "start": "1:01 AM",
            "end": "5:59 AM",
            "gate": "79",
            "door": None,
            "note": None,
        },
    ],
    "126": [
        {
            "start_min": 6 * 60,
            "end_min": 22 * 60,
            "start": "6:00 AM",
            "end": "10:00 PM",
            "gate": "213",
            "door": None,
            "note": "except_l",
        },
        {
            "start_min": 6 * 60,
            "end_min": 22 * 60,
            "start": "6:00 AM",
            "end": "10:00 PM",
            "gate": "214",
            "door": None,
            "note": "l_only",
        },
        {
            "start_min": 22 * 60 + 1,
            "end_min": 1 * 60,
            "start": "10:01 PM",
            "end": "1:00 AM",
            "gate": "323",
            "door": None,
            "note": "all",
        },
        {
            "start_min": 1 * 60 + 1,
            "end_min": 5 * 60 + 59,
            "start": "1:01 AM",
            "end": "5:59 AM",
            "gate": "79",
            "door": None,
            "note": "all",
        },
    ],
}


def builtin_schedule_payload() -> dict:
    return {
        "source": PABT_GATES_BASE_URL,
        "updated_at": "builtin",
        "routes": {k: [dict(w) for w in v] for k, v in _BUILTIN_ROUTES.items()},
        "errors": {},
    }


def load_schedule_data(*, path: str | None = None) -> dict:
    data_path = path or _DATA_PATH
    try:
        with open(data_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict) and isinstance(raw.get("routes"), dict):
            return raw
    except (OSError, ValueError, TypeError):
        pass
    return builtin_schedule_payload()


def save_schedule_data(payload: dict, *, path: str | None = None) -> str:
    data_path = path or _DATA_PATH
    # Merge: keep prior routes if a scrape partially failed.
    prior = load_schedule_data(path=data_path)
    merged_routes = dict(prior.get("routes") or {})
    merged_routes.update(payload.get("routes") or {})
    out = {
        "source": payload.get("source") or PABT_GATES_BASE_URL,
        "updated_at": payload.get("updated_at")
        or datetime.datetime.now().isoformat(timespec="seconds"),
        "routes": merged_routes,
        "errors": payload.get("errors") or {},
    }
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return data_path


def refresh_schedules_from_web(
    *, fetch_html: FetchHtml | None = None, path: str | None = None
) -> dict:
    """Scrape site, persist JSON, return saved payload."""
    payload = scrape_all_schedules(fetch_html=fetch_html)
    save_schedule_data(payload, path=path)
    return load_schedule_data(path=path)


# ---------------------------------------------------------------------------
# Resolve gates at a timestamp
# ---------------------------------------------------------------------------


def windows_for_route(route: str, *, data: dict | None = None) -> list[dict]:
    payload = data if data is not None else load_schedule_data()
    routes = payload.get("routes") or {}
    windows = routes.get(str(route)) or _BUILTIN_ROUTES.get(str(route)) or []
    return [dict(w) for w in windows]


def active_windows(
    route: str,
    *,
    now: datetime.datetime | None = None,
    data: dict | None = None,
) -> list[dict]:
    now = now or datetime.datetime.now()
    now_min = now.hour * 60 + now.minute
    return [
        w
        for w in windows_for_route(route, data=data)
        if window_contains(w["start_min"], w["end_min"], now_min)
    ]


def gate_label(window: dict) -> str:
    gate = window.get("gate") or "?"
    door = window.get("door")
    note = window.get("note")
    parts = ["Gate %s" % gate]
    if door:
        parts.append("Door %s" % door)
    if note == "except_l":
        parts.append('except "L"')
    elif note == "l_only":
        parts.append('"L" only')
    elif note and note != "all":
        parts.append(str(note))
    return " · ".join(parts)


def window_range_label(window: dict) -> str:
    return "%s – %s" % (window.get("start") or "?", window.get("end") or "?")


def format_schedule_updated_at(
    updated_at: str | None,
    *,
    now: datetime.datetime | None = None,
) -> str | None:
    """Turn ISO ``updated_at`` into a short UI stamp (e.g. ``4:12 AM``).

    Same calendar day → time only. Other day → ``Aug 3, 4:12 AM``.
    """
    if not updated_at or updated_at == "builtin":
        return None
    raw = str(updated_at).strip()
    try:
        # Accept ``2026-08-03T04:12:00`` and with offset / Z.
        parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
    except ValueError:
        return raw
    now = now or datetime.datetime.now()
    time_text = parsed.strftime("%I:%M %p").lstrip("0")
    if parsed.date() == now.date():
        return time_text
    # %-d is POSIX-only; strip leading zero from day for Windows too.
    day = parsed.strftime("%d").lstrip("0") or "0"
    return "%s %s, %s" % (parsed.strftime("%b"), day, time_text)


def resolve_gate_for_departure(
    route: str,
    destination: str | None = None,
    *,
    now: datetime.datetime | None = None,
    data: dict | None = None,
) -> dict | None:
    """Pick the gate window matching route (+ 126 L vs non-L when relevant)."""
    active = active_windows(route, now=now, data=data)
    if not active:
        return None
    if str(route) != "126" or len(active) == 1:
        return active[0]
    want_l = is_126_l_trip(destination)
    for window in active:
        note = window.get("note")
        if want_l and note == "l_only":
            return window
        if not want_l and note == "except_l":
            return window
        if note == "all":
            return window
    return active[0]


# ---------------------------------------------------------------------------
# UI boards
# ---------------------------------------------------------------------------


def _empty_board(label: str, *, note: str | None = None, error: str | None = None) -> dict:
    return {
        "label": label,
        "trains": [],
        "note": note,
        "error": error,
        "by_line": True,
        "source": "pabt_gates",
    }


def build_current_gate_boards(
    *, now: datetime.datetime | None = None, data: dict | None = None
) -> list[dict]:
    now = now or datetime.datetime.now()
    data = data if data is not None else load_schedule_data()
    boards: list[dict] = []
    for route in PABT_GATE_ROUTES:
        active = active_windows(route, now=now, data=data)
        if not active:
            boards.append(_empty_board(route, note="no gate window"))
            continue
        trains = []
        for window in active:
            trains.append(
                {
                    "minutes": 0,
                    "eta": "Gate %s" % (window.get("gate") or "?"),
                    "destination": window_range_label(window)
                    + (
                        ""
                        if not window.get("door")
                        else " · Door %s" % window["door"]
                    )
                    + (
                        ' · except "L"'
                        if window.get("note") == "except_l"
                        else (
                            ' · "L" only'
                            if window.get("note") == "l_only"
                            else ""
                        )
                    ),
                    "status": "ON_TIME",
                    "gate": window.get("gate"),
                }
            )
        boards.append(
            {
                "label": route,
                "trains": trains,
                "error": None,
                "by_line": True,
                "source": "pabt_gates",
                "note": None,
            }
        )
    return boards


def annotate_pabt_board_with_gates(
    board: dict,
    *,
    now: datetime.datetime | None = None,
    data: dict | None = None,
) -> dict:
    """Copy a PABT dep Transit board and append gate to each destination."""
    now = now or datetime.datetime.now()
    data = data if data is not None else load_schedule_data()
    out = dict(board or {})
    trains = []
    for train in list(out.get("trains") or []):
        row = dict(train)
        route = str(row.get("line") or "")
        window = resolve_gate_for_departure(
            route, row.get("destination"), now=now, data=data
        )
        if window:
            gate = window.get("gate") or "?"
            dest = str(row.get("destination") or "").strip()
            suffix = "Gate %s" % gate
            if window.get("door"):
                suffix += " · Door %s" % window["door"]
            row["destination"] = ("%s · %s" % (dest, suffix)) if dest else suffix
            row["gate"] = gate
        trains.append(row)
    out["trains"] = trains
    return out


def build_pabt_gates_sections(
    *,
    now: datetime.datetime | None = None,
    data: dict | None = None,
    scrape: bool = False,
    fetch_html: FetchHtml | None = None,
    data_path: str | None = None,
) -> list[dict]:
    """Sections for the PABT tab (current gate windows only).

    ``scrape=True`` re-fetches portauthoritygate.com and updates the JSON snapshot.
    Live PABT departures stay on HOB↔MT (annotated via ``annotate_pabt_board_with_gates``).
    """
    path = data_path
    scrape_error = None
    if scrape:
        try:
            data = refresh_schedules_from_web(fetch_html=fetch_html, path=path)
        except Exception as exc:
            scrape_error = str(exc)
            data = load_schedule_data(path=path)
    elif data is None:
        data = load_schedule_data(path=path)

    now = now or datetime.datetime.now()
    current = build_current_gate_boards(now=now, data=data)
    if scrape_error:
        # Surface scrape failure on first current-gate board note.
        if current:
            note = current[0].get("note")
            msg = "scrape failed: %s" % scrape_error
            current[0]["note"] = ("%s · %s" % (note, msg)) if note else msg
        else:
            current = [_empty_board("gates", error=scrape_error)]

    # Stamp when gates were resolved for display (not JSON scrape age — that only
    # changes on Refresh and was stuck at the shipped snapshot time).
    stamp = format_schedule_updated_at(
        now.isoformat(timespec="seconds"), now=now
    )
    return [
        {
            "title": SECTION_CURRENT + ((" · %s" % stamp) if stamp else ""),
            "boards": current,
        }
    ]
