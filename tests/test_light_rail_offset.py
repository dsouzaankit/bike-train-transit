# -*- coding: utf-8 -*-
"""Unit tests for HBLR ↔ PATH transfer offset logic."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.hblr_path import (  # noqa: E402
    HBLR_LSP_NEWPORT_OFFSET,
    HBLR_PATH_MAX_TRAINS,
    apply_transfer_filter,
    path_catchable_after_lsp,
    resolve_transfer_board,
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
        self.assertEqual(out["note"], "LSP HBLR +11")

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

    def test_newport_catchable_after_midnight_wrap(self):
        """Late evening: HBLR pool must include post-midnight PDF times for PATH +13."""
        import datetime

        from lib.light_rail import get_hblr_board

        now = datetime.datetime(2026, 6, 28, 23, 32)
        secondary = get_hblr_board(
            "Newport",
            "to_liberty_state_park",
            now=now,
            max_trains=3,
            raw_pool=36,
            force_offline=True,
        )
        raw = secondary.get("_raw_trains") or []
        self.assertGreater(len(raw), 6, msg="expected wrapped overnight pool")
        self.assertGreater(max(t["minutes"] for t in raw), 30)
        primary = _board("Chris St", [9], raw=[9])
        out = apply_transfer_filter(primary, secondary, 13, "Chris St", "Newport HBLR")
        self.assertTrue(out["trains"], msg="PATH+13 should match overnight HBLR")

    def test_caps_to_max_trains(self):
        primary = _board("WTC", [0])
        secondary = _board("Exchange Place", list(range(7, 20)), raw=list(range(7, 20)))
        out = apply_transfer_filter(primary, secondary, 7, "WTC", "Exchange Place HBLR")
        self.assertEqual(len(out["trains"]), HBLR_PATH_MAX_TRAINS)

    def test_sched_prefix_on_estimated(self):
        primary = _board("LSP", [5])
        secondary = _board("Exchange Place", [20], estimated=True)
        out = apply_transfer_filter(primary, secondary, 11, "LSP HBLR", "Exchange Place")
        self.assertEqual(out["note"], "sched · LSP HBLR +11")

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
        self.assertEqual(out["note"], "LSP HBLR +21 · current PATH")

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
        self.assertEqual(out["note"], "sched · LSP HBLR +21")


class PathCatchableAfterLspTests(unittest.TestCase):
    def test_newport_catchable_after_lsp_plus_transit(self):
        lsp = _board("Liberty State Park", [4])
        path = _board("Newport PATH", [6, 11], raw=[6, 11, 18, 25, 30], source="panynj")
        transit = _board("Newport PATH", [18, 25, 30], raw=[18, 25, 30], source="transit")
        with mock.patch("lib.path_trains.get_path_transit_board", return_value=transit):
            out = path_catchable_after_lsp(
                lsp,
                path,
                HBLR_LSP_NEWPORT_OFFSET,
                "Newport",
                transit_fetcher=lambda: transit,
            )
        self.assertEqual(_mins(out), [25, 30])
        self.assertEqual(out["note"], "LSP HBLR +21")

    @mock.patch("lib.path_trains.get_path_transit_board", return_value=None)
    def test_newport_empty_when_too_early_from_lsp(self, _transit_mock):
        lsp = _board("Liberty State Park", [5])
        path = _board("Newport PATH", [10], raw=[10], source="panynj")
        out = path_catchable_after_lsp(
            lsp,
            path,
            HBLR_LSP_NEWPORT_OFFSET,
            "Newport",
            transit_fetcher=lambda: None,
        )
        self.assertEqual(out["trains"], [])
        self.assertEqual(out["note"], "LSP HBLR +21")


class ResolveTransferBoardTests(unittest.TestCase):
    def test_path_transit_retry_on_secondary(self):
        primary = _board("Liberty State Park", [5])
        secondary = _board("Exchange Place", [6, 11], raw=[6, 11], source="panynj")
        transit_board = _board(
            "Exchange Place",
            [18, 24],
            raw=[18, 24, 30],
            source="transit",
        )
        with mock.patch("lib.path_trains.get_path_transit_board", return_value=transit_board):
            out = resolve_transfer_board(
                primary,
                secondary,
                11,
                "LSP HBLR",
                "Exchange Place",
                transit_secondary_fetcher=lambda: transit_board,
                fallback_current=True,
                fallback_suffix="PATH",
            )
        self.assertEqual(_mins(out), [18, 24, 30])

    def test_path_fallback_when_transit_unavailable(self):
        primary = _board("Liberty State Park", [5])
        secondary = _board("Newport PATH", [6, 11], raw=[6, 11], source="panynj")
        with mock.patch("lib.path_trains.get_path_transit_board", return_value=None):
            out = resolve_transfer_board(
                primary,
                secondary,
                21,
                "LSP HBLR",
                "Newport",
                transit_secondary_fetcher=lambda: None,
                fallback_current=True,
                fallback_suffix="PATH",
            )
        self.assertEqual(_mins(out), [6, 11])
        self.assertEqual(out["note"], "LSP HBLR +21 · current PATH")

    def test_skips_transit_retry_when_already_transit(self):
        primary = _board("Liberty State Park", [5])
        secondary = _board("Exchange Place", [6], raw=[6, 18], source="transit")
        fetch_mock = mock.Mock(return_value=_board("Exchange Place", [30], raw=[30]))
        with mock.patch("lib.path_trains.get_path_transit_board", fetch_mock):
            out = resolve_transfer_board(
                primary,
                secondary,
                11,
                "LSP HBLR",
                "Exchange Place",
                transit_secondary_fetcher=fetch_mock,
                fallback_current=True,
                fallback_suffix="PATH",
            )
        fetch_mock.assert_not_called()
        self.assertEqual(_mins(out), [18])

    def test_hblr_fallback_shows_current_when_no_catchable(self):
        primary = _board("WTC", [3])
        secondary = _board("Exchange Place", [5, 9], raw=[5, 9], source="transit")
        out = resolve_transfer_board(
            primary,
            secondary,
            7,
            "WTC",
            "Exchange Place HBLR",
            fallback_current=True,
            fallback_suffix="HBLR",
        )
        self.assertEqual(_mins(out), [5, 9])
        self.assertEqual(out["note"], "WTC +7 · current HBLR")

    def test_no_hblr_fallback_for_pdf_secondary(self):
        primary = _board("WTC", [3])
        secondary = _board("Exchange Place", [5, 9], raw=[5, 9], estimated=True, source="pdf")
        out = resolve_transfer_board(
            primary,
            secondary,
            7,
            "WTC",
            "Exchange Place HBLR",
            fallback_current=True,
            fallback_suffix="HBLR",
        )
        self.assertEqual(_mins(out), [])
        self.assertEqual(out["note"], "sched · WTC +7")


if __name__ == "__main__":
    unittest.main(verbosity=2)
