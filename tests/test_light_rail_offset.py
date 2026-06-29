# -*- coding: utf-8 -*-
"""Unit tests for HBLR ↔ PATH transfer offset logic."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.hblr_path import (  # noqa: E402
    HBLR_PATH_MAX_TRAINS,
    apply_transfer_filter,
)


def _board(label, minutes, raw=None, **extra):
    board = {
        "label": label,
        "trains": [{"minutes": m, "destination": "WTC", "eta": "%dm" % m} for m in minutes],
        "error": None,
    }
    if raw is not None:
        board["_raw_trains"] = [{"minutes": m, "destination": "WTC", "eta": "%dm" % m} for m in raw]
    board.update(extra)
    return board


def _mins(board):
    return [t["minutes"] for t in board["trains"]]


class TransferFilterTests(unittest.TestCase):
    def test_hblr_to_wtc_offset(self):
        primary = _board("Liberty State Park", [5, 12])
        secondary = _board("Exchange Place", [10, 20, 25], raw=[10, 20, 25])
        out = apply_transfer_filter(primary, secondary, 11, "LSP HBLR", "Exchange Place")
        self.assertEqual(_mins(out), [20, 25])
        self.assertEqual(out["note"], "after LSP HBLR +11")

    def test_path_to_hblr_offset(self):
        primary = _board("WTC", [3])
        secondary = _board("Exchange Place", [5, 9, 12], raw=[5, 9, 12])
        out = apply_transfer_filter(primary, secondary, 7, "WTC", "Exchange Place HBLR")
        self.assertEqual(_mins(out), [12])

    def test_newport_33rd_offset(self):
        primary = _board("Liberty State Park", [0])
        secondary = _board("Newport PATH", [15, 18, 25], raw=[15, 18, 25])
        out = apply_transfer_filter(primary, secondary, 21, "LSP HBLR", "Newport")
        self.assertEqual(_mins(out), [25])

    def test_no_primary_yields_note(self):
        primary = _board("Chris St", [])
        secondary = _board("Newport", [10, 20])
        out = apply_transfer_filter(primary, secondary, 13, "Chris St", "Newport HBLR")
        self.assertEqual(out["note"], "no Chris St yet")
        self.assertEqual(_mins(out), [10, 20])

    def test_caps_to_max_trains(self):
        primary = _board("WTC", [0])
        secondary = _board("Exchange Place", list(range(7, 20)), raw=list(range(7, 20)))
        out = apply_transfer_filter(primary, secondary, 7, "WTC", "Exchange Place HBLR")
        self.assertEqual(len(out["trains"]), HBLR_PATH_MAX_TRAINS)

    def test_sched_prefix_on_estimated(self):
        primary = _board("LSP", [5])
        secondary = _board("Exchange Place", [20], estimated=True)
        out = apply_transfer_filter(primary, secondary, 11, "LSP HBLR", "Exchange Place")
        self.assertEqual(out["note"], "sched · after LSP HBLR +11")

    def test_hblr_to_path_fallback_shows_current_path_etas(self):
        primary = _board("Liberty State Park", [5])
        secondary = _board("Newport PATH", [6, 11], raw=[6, 11])
        out = apply_transfer_filter(
            primary,
            secondary,
            21,
            "LSP HBLR",
            "Newport",
            fallback_current=True,
        )
        self.assertEqual(_mins(out), [6, 11])
        self.assertEqual(out["note"], "after LSP HBLR +21 · current PATH")

    def test_hblr_to_path_no_fallback_when_path_is_scheduled(self):
        primary = _board("Liberty State Park", [5])
        secondary = _board("Newport PATH", [6, 11], raw=[6, 11], estimated=True)
        out = apply_transfer_filter(
            primary,
            secondary,
            21,
            "LSP HBLR",
            "Newport",
            fallback_current=True,
        )
        self.assertEqual(_mins(out), [])
        self.assertEqual(out["note"], "sched · after LSP HBLR +21")


if __name__ == "__main__":
    unittest.main(verbosity=2)
