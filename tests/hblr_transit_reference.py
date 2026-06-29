# -*- coding: utf-8 -*-
"""Shared helpers: Transit App HBLR fixtures vs PDF offline schedule."""

from __future__ import annotations

import datetime
import json
import os

from lib import hblr_schedule
from lib import transit_app
from lib.light_rail import (
    HBLR_STATIONS,
    _destination_filter,
    _short_destination,
    get_hblr_board,
)

# Upstream HBLR boards used live in the HBLR↔PATH tab (one Transit API call each).
LIVE_HBLR_BOARDS = (
    {
        "id": "lsp_northbound",
        "station": "Liberty State Park",
        "direction": "northbound",
    },
    {
        "id": "exchange_southbound",
        "station": "Exchange Place",
        "direction": "to_liberty_state_park",
    },
    {
        "id": "newport_southbound",
        "station": "Newport",
        "direction": "to_liberty_state_park",
    },
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "transit_hblr")
MANIFEST_PATH = os.path.join(FIXTURE_DIR, "manifest.json")

# Scheduled Transit times should match PDF within this window (minutes).
PDF_BOARD_TOLERANCE_MIN = 3
# First N catchable departures to cross-check per fixture.
REFERENCE_TRAIN_COUNT = 6
# Weekday PDF columns often omit this range (NJT footnote: continuous 10–20 min headway).
WEEKDAY_PDF_GAP_START = 9 * 60 + 30
WEEKDAY_PDF_GAP_END = 15 * 60 + 30


def fixture_path(fixture_id: str) -> str:
    return os.path.join(FIXTURE_DIR, "%s.json" % fixture_id)


def load_manifest() -> dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_fixture(fixture_id: str) -> dict:
    with open(fixture_path(fixture_id), "r", encoding="utf-8") as fh:
        return json.load(fh)


def list_fixture_ids() -> list[str]:
    return [entry["id"] for entry in load_manifest().get("fixtures", [])]


def _clock_minute_from_epoch(epoch: int) -> int:
    dt = datetime.datetime.fromtimestamp(epoch)
    return dt.hour * 60 + dt.minute


def extract_reference_departures(fixture: dict, *, max_trains: int = REFERENCE_TRAIN_COUNT) -> tuple[datetime.datetime, list[dict]]:
    """Parse a saved stop_departures payload into short-dest ETAs at captured_at."""
    captured_at = int(fixture["captured_at"])
    now_dt = datetime.datetime.fromtimestamp(captured_at)
    direction = fixture["direction"]
    dest_ok = _destination_filter(direction)
    payload = fixture["payload"]
    now_epoch = captured_at

    trains: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for route in payload.get("route_departures") or []:
        for merged in route.get("merged_itineraries") or []:
            headsign_by_itin = {
                it.get("internal_itinerary_id"): (
                    it.get("headsign") or it.get("direction_headsign")
                )
                for it in merged.get("itineraries") or []
                if isinstance(it, dict)
            }
            for item in merged.get("schedule_items") or []:
                if not isinstance(item, dict) or item.get("is_cancelled"):
                    continue
                departure = item.get("departure_time")
                if departure is None:
                    continue
                minutes = transit_app._minutes_until(departure, now_epoch)
                if minutes is None:
                    continue
                headsign = headsign_by_itin.get(item.get("internal_itinerary_id"))
                if not headsign or not dest_ok(headsign):
                    continue
                short = _short_destination(headsign)
                key = (minutes, short)
                if key in seen:
                    continue
                seen.add(key)
                trains.append(
                    {
                        "destination": short,
                        "minutes": minutes,
                        "departure_epoch": int(departure),
                        "clock_minute": _clock_minute_from_epoch(int(departure)),
                    }
                )
    trains.sort(key=lambda t: (t["minutes"], t["destination"]))
    return now_dt, trains[:max_trains]


def pdf_board_at(station: str, direction: str, when: datetime.datetime, *, raw_pool: int = 36) -> list[tuple[str, int]]:
    board = get_hblr_board(
        station,
        direction,
        now=when,
        max_trains=12,
        raw_pool=raw_pool,
        force_offline=True,
    )
    return [(t["destination"], t["minutes"]) for t in board.get("trains") or []]


def pdf_explicit_minutes(station: str, direction: str, when: datetime.datetime) -> list[int]:
    return hblr_schedule.departure_minutes(station, direction, when)


def match_pdf_board(
    reference: list[dict],
    pdf_pairs: list[tuple[str, int]],
    *,
    tolerance: int = PDF_BOARD_TOLERANCE_MIN,
) -> list[str]:
    """Return human-readable mismatches (empty = OK)."""
    errors: list[str] = []
    for train in reference:
        dest = train["destination"]
        target = train["minutes"]
        matches = [
            pdf_m
            for pdf_dest, pdf_m in pdf_pairs
            if pdf_dest == dest and abs(pdf_m - target) <= tolerance
        ]
        if not matches:
            errors.append(
                "%s +%sm not in PDF board %s (tolerance ±%s)"
                % (dest, target, pdf_pairs[:8], tolerance)
            )
    return errors


def is_weekday_pdf_gap(when: datetime.datetime, clock_minute: int) -> bool:
    if when.weekday() >= 5:
        return False
    return WEEKDAY_PDF_GAP_START <= clock_minute <= WEEKDAY_PDF_GAP_END


def is_in_pdf_explicit(clock_minute: int, explicit: list[int], *, tolerance: int = 1) -> bool:
    if clock_minute in explicit:
        return True
    return any(abs(clock_minute - minute) <= tolerance for minute in explicit)


def match_pdf_explicit_times(
    reference: list[dict],
    explicit: list[int],
    when: datetime.datetime,
    *,
    tolerance: int = 1,
) -> list[str]:
    """Transit departures must appear in PDF times unless in a known weekday gap."""
    errors: list[str] = []
    now_mod = when.hour * 60 + when.minute
    for train in reference:
        clock = train["clock_minute"]
        if is_in_pdf_explicit(clock, explicit, tolerance=tolerance):
            continue
        if is_weekday_pdf_gap(when, clock):
            continue
        delta = hblr_schedule.minutes_until_departure(clock, now_mod)
        if delta is not None and delta == train["minutes"]:
            continue
        errors.append(
            "%s at clock %s (+%sm) missing from PDF (not in weekday gap %s–%s)"
            % (
                train["destination"],
                _fmt_clock(clock),
                train["minutes"],
                _fmt_clock(WEEKDAY_PDF_GAP_START),
                _fmt_clock(WEEKDAY_PDF_GAP_END),
            )
        )
    return errors


def _fmt_clock(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return "%d:%02d %s" % (hour12, minute, suffix)


def transit_stop_id(station_label: str) -> str | None:
    station = HBLR_STATIONS.get(station_label) or {}
    return station.get("transit_stop_id")
