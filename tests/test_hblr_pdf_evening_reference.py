# -*- coding: utf-8 -*-
"""Evening HBLR departures manually verified vs PDF-backed offline schedule.

Reference evening: Sunday 2026-06-28 (~8:25 PM observation window).
Sources compared: NJT/Google Maps station boards vs lib/hblr_schedule_data.json
(parsed from the NJT PDF) and get_hblr_board() offline fallback.
"""

from __future__ import annotations

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import hblr_schedule  # noqa: E402
from lib.light_rail import get_hblr_board  # noqa: E402

# When the manual list was captured (weekend service).
REFERENCE_DAY = datetime.datetime(2026, 6, 28, 12, 0)
# "Now" ~30 min before the first listed departure.
REFERENCE_NOW = datetime.datetime(2026, 6, 28, 20, 25)

DEST_ALIASES = {
    "Tonnelle Avenue": "Tonnelle Av",
    "Hoboken Terminal": "Hoboken",
    "8th Street": "8th St",
    "West Side Avenue": "West Side Av",
}

BRANCH_BY_DEST = {
    "8th St": "8th Street",
    "West Side Av": "West Side Ave",
}


def pm_to_minutes(text: str) -> int:
    """Convert '8:55 PM' to minutes from midnight."""
    body, meridiem = text.split()
    hour, minute = map(int, body.split(":"))
    if meridiem.upper() == "PM" and hour != 12:
        hour += 12
    if meridiem.upper() == "AM" and hour == 12:
        hour = 0
    return hour * 60 + minute


def fmt_clock(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return "%d:%02d %s" % (hour12, minute, suffix)


# (station, travel_direction, destination label, departure clock)
MANUAL_EVENING_DEPARTURES = (
    ("Liberty State Park", "northbound", "Tonnelle Avenue", "8:55 PM"),
    ("Liberty State Park", "northbound", "Hoboken Terminal", "9:01 PM"),
    ("Liberty State Park", "to_liberty_state_park", "8th Street", "9:02 PM"),
    ("Liberty State Park", "to_liberty_state_park", "West Side Avenue", "9:07 PM"),
    ("Exchange Place", "northbound", "Tonnelle Avenue", "9:04 PM"),
    ("Exchange Place", "northbound", "Hoboken Terminal", "9:09 PM"),
    ("Exchange Place", "to_liberty_state_park", "8th Street", "9:14 PM"),
    ("Exchange Place", "to_liberty_state_park", "West Side Avenue", "9:19 PM"),
    ("Newport", "to_liberty_state_park", "8th Street", "9:08 PM"),
    ("Newport", "northbound", "Tonnelle Avenue", "9:11 PM"),
    ("Newport", "to_liberty_state_park", "West Side Avenue", "9:13 PM"),
    ("Newport", "northbound", "Hoboken Terminal", "9:16 PM"),
)


# Weekday evening reference — fill in after manual NJT/Google Maps check (Tue–Fri).
# Use the same 12 rows as MANUAL_EVENING_DEPARTURES; pick a weekday ~8:25 PM "now".
WEEKDAY_REFERENCE_DAY = None  # e.g. datetime.datetime(2026, 6, 24, 12, 0)  # Tuesday
WEEKDAY_REFERENCE_NOW = None  # e.g. datetime.datetime(2026, 6, 24, 20, 25)
MANUAL_WEEKDAY_EVENING_DEPARTURES: tuple = ()  # same shape as MANUAL_EVENING_DEPARTURES


class HblrPdfWeekdayEveningReferenceTests(unittest.TestCase):
    """Optional weekday cross-check once MANUAL_WEEKDAY_EVENING_DEPARTURES is filled in."""

    @unittest.skipUnless(
        WEEKDAY_REFERENCE_DAY and MANUAL_WEEKDAY_EVENING_DEPARTURES,
        "weekday manual reference not yet provided",
    )
    def test_pdf_raw_times_match_manual_weekday_evening_reference(self):
        for station, direction, dest_label, clock_text in MANUAL_WEEKDAY_EVENING_DEPARTURES:
            clock_min = pm_to_minutes(clock_text)
            with self.subTest(station=station, direction=direction, dest=dest_label, time=clock_text):
                times = hblr_schedule.departure_minutes(
                    station, direction, WEEKDAY_REFERENCE_DAY
                )
                self.assertIn(
                    clock_min,
                    times,
                    msg="expected %s %s at %s on weekday PDF"
                    % (station, dest_label, clock_text),
                )


class HblrPdfEveningReferenceTests(unittest.TestCase):
    def test_pdf_data_includes_evening_service(self):
        """Parser should capture PM times, not stop near noon."""
        north = hblr_schedule.departure_minutes(
            "Liberty State Park", "northbound", REFERENCE_DAY
        )
        self.assertGreater(max(north), 20 * 60, msg="latest north LSP %s" % fmt_clock(max(north)))

        south_terminal = hblr_schedule.departure_minutes(
            "8th Street", "to_liberty_state_park", REFERENCE_DAY
        )
        self.assertGreater(
            max(south_terminal),
            20 * 60,
            msg="latest 8th St terminal %s" % fmt_clock(max(south_terminal)),
        )

    def test_pdf_raw_times_match_manual_evening_reference(self):
        for station, direction, dest_label, clock_text in MANUAL_EVENING_DEPARTURES:
            clock_min = pm_to_minutes(clock_text)
            with self.subTest(station=station, direction=direction, dest=dest_label, time=clock_text):
                if direction == "northbound":
                    times = hblr_schedule.departure_minutes(station, direction, REFERENCE_DAY)
                    self.assertIn(
                        clock_min,
                        times,
                        msg="expected %s %s north at %s in PDF times"
                        % (station, dest_label, clock_text),
                    )
                else:
                    times = hblr_schedule.departure_minutes(
                        station, direction, REFERENCE_DAY
                    )
                    self.assertIn(
                        clock_min,
                        times,
                        msg="expected %s toward %s at %s in PDF south column"
                        % (station, dest_label, clock_text),
                    )

    def test_lsp_north_branch_labels_exchanged(self):
        """LSP north: Tonnelle then Hoboken per PDF cycle (not default Hoboken first)."""
        now = datetime.datetime(2026, 6, 28, 20, 25)
        board = get_hblr_board(
            "Liberty State Park",
            "northbound",
            now=now,
            max_trains=10,
            raw_pool=80,
        )
        pairs = [(t["destination"], t["minutes"]) for t in board.get("trains") or []]
        self.assertIn(("Tonnelle Av", 30), pairs)
        self.assertIn(("Hoboken", 36), pairs)

    def test_lsp_south_evening_branch_labels(self):
        """LSP south ~8:25 PM: 8th St then West Side Av at +37 / +42."""
        now = datetime.datetime(2026, 6, 28, 20, 25)
        board = get_hblr_board(
            "Liberty State Park",
            "to_liberty_state_park",
            now=now,
            max_trains=10,
            raw_pool=36,
        )
        pairs = [(t["destination"], t["minutes"]) for t in board.get("trains") or []]
        self.assertIn(("8th St", 37), pairs)
        self.assertIn(("West Side Av", 42), pairs)

    def test_lsp_overnight_south_8th_at_1244_am(self):
        """Weekday midnight: 8th St at 12:44 AM (not West Side)."""
        now = datetime.datetime(2026, 6, 29, 0, 0)
        board = get_hblr_board(
            "Liberty State Park",
            "to_liberty_state_park",
            now=now,
            max_trains=10,
            raw_pool=36,
        )
        pairs = [(t["destination"], t["minutes"]) for t in board.get("trains") or []]
        self.assertIn(("8th St", 44), pairs)
        self.assertNotIn(("West Side Av", 44), pairs)

    def test_newport_overnight_explicit_times(self):
        """Weekday ~midnight: Newport uses PDF times (8th ~12:38 AM from 23:50)."""
        now = datetime.datetime(2026, 6, 29, 23, 50)
        board = get_hblr_board(
            "Newport",
            "to_liberty_state_park",
            now=now,
            max_trains=12,
            raw_pool=36,
        )
        pairs = [(t["destination"], t["minutes"]) for t in board.get("trains") or []]
        self.assertIn(("8th St", 48), pairs)
        for _dest, delta in pairs:
            self.assertGreaterEqual(delta, 0)

    def test_exchange_place_north_branch_labels_exchanged(self):
        """Exchange Place north: Tonnelle then Hoboken per PDF cycle."""
        now = datetime.datetime(2026, 6, 28, 20, 25)
        board = get_hblr_board(
            "Exchange Place",
            "northbound",
            now=now,
            max_trains=10,
            raw_pool=80,
        )
        pairs = [(t["destination"], t["minutes"]) for t in board.get("trains") or []]
        self.assertIn(("Tonnelle Av", 39), pairs)
        self.assertIn(("Hoboken", 44), pairs)

    def test_exchange_place_overnight_south_8th_at_1244_am(self):
        """Weekday ~midnight: 8th St at 12:44 AM (Gmaps), not afternoon ghost times."""
        now = datetime.datetime(2026, 6, 29, 23, 50)
        board = get_hblr_board(
            "Exchange Place",
            "to_liberty_state_park",
            now=now,
            max_trains=12,
            raw_pool=36,
        )
        pairs = [(t["destination"], t["minutes"]) for t in board.get("trains") or []]
        self.assertIn(("8th St", 54), pairs)
        self.assertNotIn(("West Side Av", 54), pairs)
        for _dest, delta in pairs:
            self.assertGreaterEqual(delta, 0, msg="no negative ETAs: %s" % pairs)

    def test_newport_matches_manual_evening_reference(self):
        """Newport north/south labels and times vs Google Maps / PDF (Sun ~8:25 PM)."""
        now = datetime.datetime(2026, 6, 28, 20, 25)
        north = get_hblr_board(
            "Newport",
            "northbound",
            now=now,
            max_trains=10,
            raw_pool=80,
        )
        north_pairs = [(t["destination"], t["minutes"]) for t in north.get("trains") or []]
        self.assertIn(("Tonnelle Av", 46), north_pairs)
        self.assertIn(("Hoboken", 51), north_pairs)

        south = get_hblr_board(
            "Newport",
            "to_liberty_state_park",
            now=now,
            max_trains=10,
            raw_pool=80,
        )
        south_pairs = [(t["destination"], t["minutes"]) for t in south.get("trains") or []]
        self.assertIn(("8th St", 43), south_pairs)
        self.assertIn(("West Side Av", 48), south_pairs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
