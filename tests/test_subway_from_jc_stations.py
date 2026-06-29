# -*- coding: utf-8 -*-
"""From JC express-at-local-station cards."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.subway_trains import (  # noqa: E402
    BLEECKER_LINE_SPECS,
    FIFTY_FIRST_LINE_SPECS,
    FIFTY_ST_LINE_SPECS,
    _annotate_express_local_board,
    _load_line_board,
    _normalize_arrival,
    _trains_per_line,
)


class ExpressLocalBoardTests(unittest.TestCase):
    def test_fifty_st_shows_a_when_express_stops(self):
        raw = [
            {"line": "A", "direction": "N", "minutes": 4, "headsign": "Inwood"},
            {"line": "C", "direction": "N", "minutes": 2, "headsign": "168 St"},
        ]
        board = _annotate_express_local_board(
            {
                "label": "50 St",
                "trains": _trains_per_line(raw, line_specs=FIFTY_ST_LINE_SPECS),
                "_raw_trains": raw,
            },
            FIFTY_ST_LINE_SPECS,
        )
        self.assertEqual(len(board["trains"]), 1)
        self.assertEqual(board["trains"][0]["line"], "A")
        self.assertEqual(board["note"], "Express local stop")

    def test_fifty_st_notes_local_only_when_a_absent(self):
        raw = [
            {"line": "C", "direction": "N", "minutes": 3, "headsign": "168 St"},
            {"line": "E", "direction": "N", "minutes": 5, "headsign": "Jamaica Center"},
        ]
        board = _annotate_express_local_board(
            {
                "label": "50 St",
                "trains": _trains_per_line(raw, line_specs=FIFTY_ST_LINE_SPECS),
                "_raw_trains": raw,
            },
            FIFTY_ST_LINE_SPECS,
        )
        self.assertEqual(board["trains"], [])
        self.assertEqual(board["note"], "Express skip · local C/E")
        self.assertEqual(board["empty_hint"], "Express not stopping")

    def test_bleecker_shows_4_5_when_express_stops(self):
        raw = [
            {"line": "4", "direction": "S", "minutes": 6, "headsign": "New Lots Av"},
            {"line": "6", "direction": "S", "minutes": 2, "headsign": "Brooklyn Bridge"},
        ]
        board = _annotate_express_local_board(
            {
                "label": "Bleecker St",
                "trains": _trains_per_line(raw, line_specs=BLEECKER_LINE_SPECS),
                "_raw_trains": raw,
            },
            BLEECKER_LINE_SPECS,
        )
        self.assertEqual(len(board["trains"]), 1)
        self.assertEqual(board["trains"][0]["line"], "4")
        self.assertEqual(board["note"], "Express local stop")

    def test_bleecker_notes_local_6_when_express_skips(self):
        raw = [{"line": "6", "direction": "S", "minutes": 4, "headsign": "Brooklyn Bridge"}]
        board = _annotate_express_local_board(
            {
                "label": "Bleecker St",
                "trains": _trains_per_line(raw, line_specs=BLEECKER_LINE_SPECS),
                "_raw_trains": raw,
            },
            BLEECKER_LINE_SPECS,
        )
        self.assertEqual(board["trains"], [])
        self.assertEqual(board["note"], "Express skip · local 6")
        self.assertEqual(board["empty_hint"], "Express not stopping")


    def test_fifty_first_notes_local_when_express_skips(self):
        raw = [{"line": "6", "direction": "N", "minutes": 4, "headsign": "Pelham Bay Park"}]
        board = _annotate_express_local_board(
            {
                "label": "51 St",
                "trains": _trains_per_line(raw, line_specs=FIFTY_FIRST_LINE_SPECS),
                "_raw_trains": raw,
            },
            FIFTY_FIRST_LINE_SPECS,
        )
        self.assertEqual(board["trains"], [])
        self.assertEqual(board["note"], "Express skip · local 6")
        self.assertEqual(board["empty_hint"], "Express not stopping")


if __name__ == "__main__":
    unittest.main(verbosity=2)
