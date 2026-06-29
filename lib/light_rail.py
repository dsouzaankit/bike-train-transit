# -*- coding: utf-8 -*-
"""Hudson-Bergen Light Rail (HBLR) departures for the HBLR↔PATH tab.

Data source (first match wins):
  1. Transit App API (transit_credentials.json / TRANSIT_API_KEY) — real-time ETAs
  2. NJ Transit Bus/Light-Rail API (njt_credentials.json) — optional fallback
  3. Parsed PDF timetable in hblr_schedule_data.json
"""

from __future__ import annotations

import datetime
import json
import os
import urllib.parse
import urllib.request

from . import hblr_schedule
from . import transit_app

NJT_BASE = "https://pcsdata.njtransit.com"
NJT_AUTH_PATH = "/api/BUSDV2/authenticateUser"
NJT_DV_PATH = "/api/BUSDV2/getBusDV"
NJT_MODE = "HBLR"
NJT_TIMEOUT = 20

SOUTHBOUND_DESTINATIONS = (
    "west side",
    "8th st",
    "8th street",
    "bayonne",
)

LIBERTY_STATE_PARK_DESTINATIONS = (
    "liberty state",
    "liberty",
)

HBLR_STATIONS = {
    # Bayonne/JC branch terminals — PDF offline schedule only (not shown in UI).
    "8th Street": {
        "label": "8th Street",
        "njt_stop": "8th Street",
        "phase": 0,
    },
    "West Side Ave": {
        "label": "West Side Ave",
        "njt_stop": "West Side Avenue",
        "phase": 0,
    },
    # Upstream stations — live boards (Transit → NJT → PDF) for HBLR↔PATH tab.
    "Liberty State Park": {
        "label": "Liberty State Park",
        "njt_stop": "Liberty State Park",
        "transit_stop_id": "NJTR:3072",
        "phase": 0,
    },
    "Exchange Place": {
        "label": "Exchange Place",
        "njt_stop": "Exchange Place",
        "transit_stop_id": "NJTR:3076",
        "phase": 3,
    },
    "Newport": {
        "label": "Newport",
        "njt_stop": "Newport",
        "transit_stop_id": "NJTR:3079",
        "phase": 0,
    },
}

HBLR_DIRECTIONS = {
    "northbound": {
        "dest_filter": "_is_northbound_destination",
        "schedule_key": None,
    },
    "to_liberty_state_park": {
        "dest_filter": "_is_towards_liberty_state_park",
        "schedule_key": "southbound",
    },
}


def _load_credentials():
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
    if transit_app.has_api_key():
        return True
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


def _is_northbound_destination(name):
    if _is_southbound_destination(name):
        return False
    text = (name or "").casefold()
    if any(token in text for token in LIBERTY_STATE_PARK_DESTINATIONS):
        return False
    return bool(text.strip())


def _is_towards_liberty_state_park(name):
    text = (name or "").casefold()
    if any(token in text for token in LIBERTY_STATE_PARK_DESTINATIONS):
        return True
    return _is_southbound_destination(name)


def _destination_filter(direction):
    spec = HBLR_DIRECTIONS.get(direction, HBLR_DIRECTIONS["northbound"])
    name = spec["dest_filter"]
    return {
        "_is_northbound_destination": _is_northbound_destination,
        "_is_towards_liberty_state_park": _is_towards_liberty_state_park,
    }[name]


def _short_destination(name):
    text = (name or "").strip()
    low = text.casefold()
    if "liberty state" in low or low == "liberty":
        return "Liberty State Pk"
    if "west side" in low:
        return "West Side Av"
    if "8th" in low:
        return "8th St"
    if "bayonne" in low:
        return "8th St"
    if "hoboken" in low:
        return "Hoboken"
    if "tonnelle" in low:
        return "Tonnelle Av"
    return text or "?"


def _fetch_transit_departures(station, direction, count):
    stop_id = station.get("transit_stop_id")
    if not stop_id or not transit_app.has_api_key():
        return None
    dest_ok = _destination_filter(direction)
    payload = transit_app.fetch_stop_departures(stop_id, max_departures=count)
    raw = transit_app.parse_route_departures(payload, dest_ok, max_trains=count)
    if not raw:
        return None
    trains = []
    for train in raw:
        entry = dict(train)
        entry["destination"] = _short_destination(train.get("destination"))
        trains.append(entry)
    return trains


def _fetch_station_departures(station, token, direction):
    dest_ok = _destination_filter(direction)
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
        if not dest_ok(dest):
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


def _offline_trains(station, direction, now=None, count=12):
    return hblr_schedule.upcoming_departures(
        station,
        travel_direction=direction,
        now=now,
        count=count,
    )


def get_hblr_board(
    station_label,
    direction,
    now=None,
    max_trains=3,
    raw_pool=12,
    force_offline=False,
):
    """Single HBLR station board for a travel direction. Never raises."""
    station = HBLR_STATIONS.get(station_label)
    if station is None:
        return {"label": station_label, "trains": [], "error": "Unknown station"}

    fetch_error = None
    pool_size = max(max_trains, raw_pool)

    live = None
    if not force_offline:
        try:
            live = _fetch_transit_departures(station, direction, pool_size)
        except Exception as exc:
            fetch_error = str(exc)

        if live:
            return {
                "label": station["label"],
                "trains": live[:max_trains],
                "_raw_trains": live,
                "error": None,
                "by_line": True,
                "source": "transit",
            }

        username, password, token = _load_credentials()
        if token or (username and password):
            try:
                if not token:
                    token = _authenticate(username, password)
                if not token:
                    raise RuntimeError("NJT auth returned no token")
                live = _fetch_station_departures(station, token, direction)
                if live:
                    return {
                        "label": station["label"],
                        "trains": live[:max_trains],
                        "_raw_trains": live,
                        "error": None,
                        "by_line": True,
                        "source": "njt",
                    }
            except Exception as exc:
                if not fetch_error:
                    fetch_error = str(exc)

    sched = _offline_trains(station, direction, now=now, count=raw_pool)
    board = {
        "label": station["label"],
        "trains": sched[:max_trains],
        "_raw_trains": sched,
        "error": None,
        "by_line": True,
        "estimated": True,
        "note": "scheduled" if sched else "no service now",
        "source": "pdf",
    }
    if fetch_error and not sched:
        board["note"] = "scheduled (live fetch failed)"
    return board
