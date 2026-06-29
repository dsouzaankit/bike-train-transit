# -*- coding: utf-8 -*-
"""Transit App public API — real-time HBLR departures (v4).

Docs: https://api-doc.transitapp.com/v4.html
Auth: apiKey header; free tier 5 req/min, 1,500 req/month.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

TRANSIT_BASE = "https://external.transitapp.com"
TRANSIT_STOP_DEPARTURES = "/v4/public/stop_departures"
TRANSIT_TIMEOUT = 20
TRANSIT_MAX_DEPARTURES = 12
# Reuse stop payloads within one refresh (HBLR tab hits the same stop once).
_CACHE_TTL_SEC = 45

_DEPARTURE_CACHE: dict[str, tuple[float, dict]] = {}


from . import credential_paths


def _load_api_key():
    key = os.environ.get("TRANSIT_API_KEY")
    if key:
        return key.strip()
    for name in ("transit_credentials.json", ".transit_credentials.json"):
        data = credential_paths.load_json_credential(name)
        if data:
            key = data.get("api_key") or data.get("apiKey")
            if key:
                return str(key).strip()
    return None


def has_api_key():
    return bool(_load_api_key())


def clear_departure_cache():
    _DEPARTURE_CACHE.clear()


def _get_json(path, params):
    key = _load_api_key()
    if not key:
        raise RuntimeError("Transit API key not configured")
    url = TRANSIT_BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "apiKey": key,
            "Accept-Language": "en",
            "User-Agent": "bike-train-transit/2.0",
        },
    )
    with urllib.request.urlopen(req, timeout=TRANSIT_TIMEOUT) as resp:
        return json.loads(resp.read())


def fetch_stop_departures(global_stop_id, *, max_departures=TRANSIT_MAX_DEPARTURES):
    """Return raw v4 stop_departures JSON for a global_stop_id."""
    now = time.time()
    cached = _DEPARTURE_CACHE.get(global_stop_id)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]
    payload = _get_json(
        TRANSIT_STOP_DEPARTURES,
        {
            "global_stop_id": global_stop_id,
            "max_num_departures": max(1, min(10, int(max_departures))),
            "should_update_realtime": "true",
        },
    )
    _DEPARTURE_CACHE[global_stop_id] = (now, payload)
    return payload


def _minutes_until(departure_epoch, now_epoch=None):
    if departure_epoch is None:
        return None
    now_epoch = now_epoch if now_epoch is not None else time.time()
    delta = int(departure_epoch) - int(now_epoch)
    if delta < 0:
        return None
    return max(0, (delta + 59) // 60)


def parse_route_departures(payload, dest_ok, *, now_epoch=None, max_trains=12):
    """Flatten v4 stop_departures into sorted train dicts for one direction filter."""
    now_epoch = now_epoch if now_epoch is not None else time.time()
    trains = []
    seen = set()
    for route in payload.get("route_departures") or []:
        if not isinstance(route, dict):
            continue
        for merged in route.get("merged_itineraries") or []:
            if not isinstance(merged, dict):
                continue
            headsigns = []
            for itinerary in merged.get("itineraries") or []:
                if not isinstance(itinerary, dict):
                    continue
                head = (
                    itinerary.get("headsign")
                    or itinerary.get("direction_headsign")
                    or itinerary.get("merged_headsign")
                )
                if head:
                    headsigns.append(head)
            for item in merged.get("schedule_items") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("is_cancelled"):
                    continue
                departure = item.get("departure_time")
                minutes = _minutes_until(departure, now_epoch)
                if minutes is None:
                    continue
                headsign = None
                internal_id = item.get("internal_itinerary_id")
                if internal_id:
                    for itinerary in merged.get("itineraries") or []:
                        if itinerary.get("internal_itinerary_id") == internal_id:
                            headsign = (
                                itinerary.get("headsign")
                                or itinerary.get("direction_headsign")
                            )
                            break
                if not headsign and headsigns:
                    headsign = headsigns[0]
                if not headsign or not dest_ok(headsign):
                    continue
                key = (minutes, headsign.casefold())
                if key in seen:
                    continue
                seen.add(key)
                eta = "Due" if minutes == 0 else "%dm" % minutes
                status = "ON_TIME"
                if item.get("is_real_time"):
                    status = "REALTIME"
                trains.append(
                    {
                        "line": None,
                        "destination": headsign,
                        "minutes": minutes,
                        "eta": eta,
                        "status": status,
                    }
                )
    trains.sort(key=lambda t: (t.get("minutes") if t.get("minutes") is not None else 9999, t.get("destination") or ""))
    return trains[: max(1, int(max_trains))]
