# -*- coding: utf-8 -*-
"""PANYNJ bridge/tunnel crossing times (Lincoln & Holland)."""

from __future__ import annotations

import time

CROSSING_TIMES_URL = "https://www.panynj.gov/bin/portauthority/crossingtimesapi.json"
TUNNEL_FACILITIES = ("Holland Tunnel", "Lincoln Tunnel")
DIRECTION_LABELS = {
    "ToNY": "→ NYC",
    "ToNJ": "→ NJ",
}


def _crossing_url():
    return CROSSING_TIMES_URL + "?_=" + str(int(time.time() * 1000))


def _primary_entry(entries):
    """Prefer the main tube (empty facilityModifier) when multiple routes exist."""
    plain = [e for e in entries if not (e.get("facilityModifier") or "").strip()]
    pool = plain or entries
    pool = [e for e in pool if e.get("isDataAvailable")]
    if not pool:
        return entries[0] if entries else None
    return pool[0]


def _normalize_entry(entry):
    minutes = entry.get("timeStatusMessage")
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = None
    status = (entry.get("infomationalText") or "—").strip()
    speed = entry.get("speedStatusMessage")
    closed = bool(entry.get("isCrossingClosed"))
    eta = "Closed" if closed else ("%s min" % minutes if minutes is not None else "?")
    return {
        "destination": DIRECTION_LABELS.get(entry.get("travelDirection"), entry.get("travelDirection")),
        "minutes": minutes,
        "eta": eta,
        "status": "CLOSED" if closed else "ON_TIME",
        "status_text": status,
        "speed_mph": speed,
        "eta_bg": entry.get("detailsUIBackgroundColor")
        or entry.get("overviewUIBackgroundColor")
        or "#2a3441",
        "eta_fg": entry.get("detailsUITextColor")
        or entry.get("overviewUITextColor")
        or "#FFFFFF",
    }


def get_tunnel_boards(fetch_json):
    """Return one board per tunnel (Holland, Lincoln) with ToNY/ToNJ rows."""
    error = None
    payload = None
    try:
        payload = fetch_json(_crossing_url())
    except Exception as exc:
        error = str(exc)

    if not isinstance(payload, list):
        boards = []
        for name in TUNNEL_FACILITIES:
            boards.append(
                {
                    "label": name,
                    "trains": [],
                    "error": error or "Unexpected crossing-times response",
                }
            )
        return boards

    boards = []
    for name in TUNNEL_FACILITIES:
        trains = []
        for direction in ("ToNY", "ToNJ"):
            matches = [
                e
                for e in payload
                if e.get("crossingDisplayName") == name
                and e.get("travelDirection") == direction
            ]
            if not matches:
                continue
            entry = _primary_entry(matches)
            if entry is not None:
                trains.append(_normalize_entry(entry))
        boards.append(
            {
                "label": name,
                "trains": trains,
                "error": None if trains else (error or "No tunnel data"),
                "source": "panynj-crossingtimes",
                "tunnel_card": True,
            }
        )
    return boards


def print_tunnel_boards(boards, title="Tunnels"):
    print(title)
    for board in boards:
        print("")
        print(board["label"])
        if board.get("error") and not board.get("trains"):
            print("  unavailable (%s)" % board["error"])
            continue
        for row in board.get("trains") or []:
            note = row.get("note") or ""
            suffix = " · %s" % note if note else ""
            print("  %s  %s%s" % (row.get("eta"), row.get("destination"), suffix))
