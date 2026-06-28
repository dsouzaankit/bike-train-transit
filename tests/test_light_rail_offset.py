# -*- coding: utf-8 -*-
"""Unit tests for the HBLR <- PATH offset/connection logic.

Run from the project root:
    python -m unittest discover -s tests
    python tests/test_light_rail_offset.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.light_rail import (  # noqa: E402
    LIGHT_RAIL_MAX_TRAINS,
    _earliest_path_minutes,
    apply_path_lightrail_connections,
)


def _hblr_board(label, minutes, raw=None, **extra):
    """Build a minimal HBLR board with trains at the given minute marks."""
    board = {
        "label": label,
        "trains": [{"minutes": m, "destination": "8th St"} for m in minutes],
        "error": None,
    }
    if raw is not None:
        board["_raw_trains"] = [{"minutes": m, "destination": "8th St"} for m in raw]
    board.update(extra)
    return board


def _path_board(label, minutes):
    return {"label": label, "trains": [{"minutes": m} for m in minutes], "error": None}


def _mins(board):
    return [t["minutes"] for t in board["trains"]]


class EarliestPathMinutesTests(unittest.TestCase):
    def test_picks_minimum(self):
        self.assertEqual(_earliest_path_minutes(_path_board("X", [9, 3, 14])), 3)

    def test_ignores_none(self):
        board = {"trains": [{"minutes": None}, {"minutes": 7}, {"minutes": None}]}
        self.assertEqual(_earliest_path_minutes(board), 7)

    def test_empty_or_missing(self):
        self.assertIsNone(_earliest_path_minutes(None))
        self.assertIsNone(_earliest_path_minutes({"trains": []}))
        self.assertIsNone(_earliest_path_minutes({"trains": [{"minutes": None}]}))


class OffsetConnectionTests(unittest.TestCase):
    def test_newport_threshold_filters_below_path_plus_offset(self):
        # Newport offset is 15; earliest Christopher St PATH at 5 -> threshold 20.
        hblr = [_hblr_board("Newport", [10, 20, 25, 40])]
        path = [_path_board("Christopher St", [5, 12])]
        out = apply_path_lightrail_connections(hblr, path)
        self.assertEqual(_mins(out[0]), [20, 25, 40])  # 10 dropped; 20 inclusive
        self.assertEqual(out[0]["note"], "after Christopher St PATH +15")

    def test_exchange_place_offset(self):
        # Exchange Place offset is 6; earliest WTC PATH at 3 -> threshold 9.
        hblr = [_hblr_board("Exchange Place", [5, 9, 12])]
        path = [_path_board("World Trade Center", [3])]
        out = apply_path_lightrail_connections(hblr, path)
        self.assertEqual(_mins(out[0]), [9, 12])
        self.assertEqual(out[0]["note"], "after World Trade Center PATH +6")

    def test_threshold_is_inclusive(self):
        hblr = [_hblr_board("Newport", [19, 20])]  # threshold 20 (path 5 + 15)
        path = [_path_board("Christopher St", [5])]
        out = apply_path_lightrail_connections(hblr, path)
        self.assertEqual(_mins(out[0]), [20])

    def test_caps_to_max_trains(self):
        hblr = [_hblr_board("Newport", [15, 16, 17, 18, 19])]  # path 0 -> threshold 15
        path = [_path_board("Christopher St", [0])]
        out = apply_path_lightrail_connections(hblr, path)
        self.assertEqual(len(out[0]["trains"]), LIGHT_RAIL_MAX_TRAINS)
        self.assertEqual(_mins(out[0]), [15, 16, 17])

    def test_uses_raw_trains_when_present(self):
        # Visible trains are pre-capped; filtering must use the larger _raw_trains.
        hblr = [_hblr_board("Newport", [20], raw=[10, 20, 30, 40])]
        path = [_path_board("Christopher St", [5])]  # threshold 20
        out = apply_path_lightrail_connections(hblr, path)
        self.assertEqual(_mins(out[0]), [20, 30, 40])

    def test_no_path_data_keeps_trains_with_note(self):
        hblr = [_hblr_board("Newport", [10, 20])]
        out = apply_path_lightrail_connections(hblr, [])  # no PATH board
        self.assertEqual(out[0]["note"], "no Christopher St PATH yet")
        self.assertEqual(_mins(out[0]), [10, 20])  # untouched

    def test_estimated_board_gets_sched_prefix(self):
        hblr = [_hblr_board("Newport", [25], estimated=True)]
        path = [_path_board("Christopher St", [5])]
        out = apply_path_lightrail_connections(hblr, path)
        self.assertEqual(out[0]["note"], "sched \u00b7 after Christopher St PATH +15")

    def test_nothing_catchable_yields_empty(self):
        hblr = [_hblr_board("Newport", [5, 10])]  # threshold 20
        path = [_path_board("Christopher St", [5])]
        out = apply_path_lightrail_connections(hblr, path)
        self.assertEqual(out[0]["trains"], [])

    def test_unmapped_board_passes_through(self):
        board = {"label": "Mystery", "trains": [{"minutes": 1}], "error": None}
        out = apply_path_lightrail_connections([board], [])
        self.assertEqual(out[0], board)


if __name__ == "__main__":
    unittest.main(verbosity=2)
