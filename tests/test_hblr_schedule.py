# -*- coding: utf-8 -*-
"""Tests for HBLR PDF timetable loading and offline departure lookup."""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import hblr_schedule  # noqa: E402
from lib.light_rail import get_hblr_board  # noqa: E402


class HblrScheduleDataTests(unittest.TestCase):
    def test_json_has_all_stations_both_directions(self):
        data = hblr_schedule._load_data()
        self.assertIsNotNone(data)
        self.assertIn("directions", data)
        for direction in ("north_to_hoboken", "south_to_bayonne"):
            self.assertIn(direction, data["directions"])
            for station in (
                "8th Street",
                "West Side Ave",
                "Newport",
                "Exchange Place",
                "Liberty State Park",
            ):
                self.assertIn(station, data["directions"][direction])
                weekday = data["directions"][direction][station]["weekday"]
                weekend = data["directions"][direction][station]["weekend"]
                self.assertGreater(len(weekday), 20, msg=f"{direction}/{station} weekday")
                self.assertGreater(len(weekend), 15, msg=f"{direction}/{station} weekend")

    def test_departure_minutes_respects_travel_direction(self):
        south = hblr_schedule.departure_minutes(
            "Liberty State Park", "to_liberty_state_park"
        )
        north = hblr_schedule.departure_minutes("Liberty State Park", "northbound")
        self.assertEqual(south, sorted(south))
        self.assertEqual(north, sorted(north))
        self.assertGreater(len(south), 50)
        self.assertGreater(len(north), 50)
        self.assertNotEqual(south, north)


class WeekendBranchHeadwayTests(unittest.TestCase):
    """Weekend 12:00–02:00: each southern branch line every 20 minutes."""

    EXPECTED_GAP = hblr_schedule.WEEKEND_BRANCH_HEADWAY
    STATIONS = tuple(hblr_schedule.SOUTH_BRANCH_OFFSETS.keys())

    def _assert_twenty_minute_line(self, offsets: list[int], label: str) -> None:
        self.assertGreaterEqual(
            len(offsets),
            2,
            msg="%s should have multiple departures in the weekend window" % label,
        )
        gaps = [offsets[index + 1] - offsets[index] for index in range(len(offsets) - 1)]
        for gap in gaps:
            self.assertEqual(
                gap,
                self.EXPECTED_GAP,
                msg="%s gap %s min (expected %s)"
                % (label, gap, self.EXPECTED_GAP),
            )

    def test_weekend_noon_to_2am_every_line_runs_every_twenty_minutes(self):
        for day in (datetime.datetime(2026, 6, 27, 12, 0), datetime.datetime(2026, 6, 28, 12, 0)):
            for station in self.STATIONS:
                lines = hblr_schedule.branch_departures_in_weekend_window(station, day)
                self.assertTrue(lines, msg="no lines for %s on %s" % (station, day.date()))
                for destination, offsets in lines.items():
                    self._assert_twenty_minute_line(
                        offsets,
                        "%s %s %s" % (day.strftime("%a"), station, destination),
                    )

    def test_weekend_board_etas_twenty_minutes_per_destination(self):
        """Runtime boards in the window should match the same 20 min spacing."""
        samples = (
            datetime.datetime(2026, 6, 27, 12, 0),
            datetime.datetime(2026, 6, 27, 18, 0),
            datetime.datetime(2026, 6, 28, 0, 30),
            datetime.datetime(2026, 6, 28, 1, 0),
        )
        for now in samples:
            board = get_hblr_board(
                "Newport",
                "to_liberty_state_park",
                now=now,
                max_trains=10,
                raw_pool=50,
            )
            by_dest: dict[str, list[int]] = {}
            for train in board.get("trains") or []:
                by_dest.setdefault(train["destination"], []).append(train["minutes"])
            for destination in ("8th St", "West Side Av"):
                deltas = sorted(by_dest.get(destination, []))
                self.assertGreaterEqual(len(deltas), 2, msg="%s at %s" % (destination, now))
                gap = deltas[1] - deltas[0]
                self.assertEqual(gap, self.EXPECTED_GAP, msg="%s at %s" % (destination, now))


class OfflineScheduleTrainsTests(unittest.TestCase):
    def test_south_uses_pdf_times(self):
        now = datetime.datetime(2026, 6, 22, 8, 0)
        board = get_hblr_board("Newport", "to_liberty_state_park", now=now, raw_pool=12)
        trains = board.get("trains") or []
        self.assertGreaterEqual(len(trains), 3)
        self.assertIn(trains[0]["destination"], ("8th St", "West Side Av"))

    def test_terminal_stations_have_pdf_times(self):
        for station, direction in (
            ("8th Street", "northbound"),
            ("West Side Ave", "northbound"),
            ("8th Street", "to_liberty_state_park"),
            ("West Side Ave", "to_liberty_state_park"),
        ):
            minutes = hblr_schedule.departure_minutes(station, direction)
            self.assertGreater(len(minutes), 20, msg=f"{station} {direction}")

    def test_north_at_lsp_uses_pdf_not_headway_only(self):
        now = datetime.datetime(2026, 6, 22, 8, 0)
        board = get_hblr_board("Liberty State Park", "northbound", now=now, raw_pool=12)
        trains = board.get("trains") or []
        self.assertGreaterEqual(len(trains), 3)
        self.assertIn(trains[0]["destination"], ("Hoboken", "Tonnelle Av"))
        explicit = hblr_schedule.departure_minutes("Liberty State Park", "northbound", now)
        now_mod = now.hour * 60 + now.minute
        expected_first = min(m - now_mod for m in explicit if m >= now_mod)
        self.assertEqual(trains[0]["minutes"], expected_first)

    def test_branch_lines_twenty_min_apart(self):
        """Each southern branch should keep ~20 min spacing, not combined trunk headway."""
        now = datetime.datetime(2026, 6, 28, 19, 0)  # Sunday 7pm
        board = get_hblr_board(
            "Newport", "to_liberty_state_park", now=now, max_trains=8, raw_pool=12
        )
        by_dest: dict[str, list[int]] = {}
        for train in board.get("trains") or []:
            by_dest.setdefault(train["destination"], []).append(train["minutes"])
        self.assertIn("8th St", by_dest)
        self.assertIn("West Side Av", by_dest)
        for dest, deltas in by_dest.items():
            self.assertGreaterEqual(len(deltas), 2, msg=dest)
            gap = deltas[1] - deltas[0]
            self.assertGreaterEqual(gap, 18, msg=f"{dest} gap {gap}")
            self.assertLessEqual(gap, 22, msg=f"{dest} gap {gap}")

    def test_headway_extends_after_last_pdf_time(self):
        now = datetime.datetime(2026, 6, 22, 14, 0)
        board = get_hblr_board("Exchange Place", "to_liberty_state_park", now=now, raw_pool=12)
        trains = board.get("trains") or []
        self.assertGreaterEqual(len(trains), 1)
        self.assertLessEqual(trains[0]["minutes"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
