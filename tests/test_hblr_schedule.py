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
    def test_json_has_both_stations(self):
        data = hblr_schedule._load_data()
        self.assertIsNotNone(data)
        for station in ("Newport", "Exchange Place"):
            self.assertIn(station, data["stations"])
            self.assertGreater(len(data["stations"][station]["weekday"]), 50)
            self.assertGreater(len(data["stations"][station]["weekend"]), 30)

    def test_departure_minutes_sorted(self):
        minutes = hblr_schedule.departure_minutes("Newport")
        self.assertEqual(minutes, sorted(minutes))
        self.assertGreaterEqual(minutes[0], 60)


class OfflineScheduleTrainsTests(unittest.TestCase):
    def test_uses_pdf_times_not_pure_headway(self):
        now = datetime.datetime(2026, 6, 22, 8, 0)
        board = get_hblr_board("Newport", "to_liberty_state_park", now=now, raw_pool=12)
        trains = board.get("trains") or []
        self.assertGreaterEqual(len(trains), 3)
        deltas = [t["minutes"] for t in trains]
        self.assertEqual(deltas, sorted(deltas))
        self.assertTrue(board.get("estimated"))
        self.assertTrue(all(t["eta"].startswith("~") or t["eta"] == "Due" for t in trains))

    def test_headway_extends_after_last_pdf_time(self):
        now = datetime.datetime(2026, 6, 22, 14, 0)
        board = get_hblr_board("Exchange Place", "to_liberty_state_park", now=now, raw_pool=12)
        trains = board.get("trains") or []
        self.assertGreaterEqual(len(trains), 1)
        self.assertLessEqual(trains[0]["minutes"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
