# -*- coding: utf-8 -*-
"""Exchange Place PATH → WTC + northbound subway connection (HBLR tab)."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.subway_trains import (  # noqa: E402
    EXCHANGE_WTC_PATH_WALK,
    apply_exchange_wtc_subway_connections,
)


class ExchangeWtcSubwayTests(unittest.TestCase):
    def test_filters_subway_after_path_plus_eight(self):
        path_board = {
            "label": "Exchange Place",
            "trains": [{"destination": "WTC", "minutes": 10, "eta": "10m"}],
        }
        subway_boards = [
            {
                "label": "WTC Cortlandt",
                "trains": [{"line": "1", "minutes": 19, "eta": "19m", "destination": "Van Cortlandt"}],
                "_raw_trains": [
                    {"line": "1", "minutes": 16, "eta": "16m", "destination": "Van Cortlandt"},
                    {"line": "1", "minutes": 19, "eta": "19m", "destination": "Van Cortlandt"},
                ],
                "by_line": True,
            },
            {
                "label": "WTC",
                "trains": [{"line": "E", "minutes": 22, "eta": "22m", "destination": "Jamaica"}],
                "_raw_trains": [
                    {"line": "E", "minutes": 17, "eta": "17m", "destination": "Jamaica"},
                    {"line": "E", "minutes": 22, "eta": "22m", "destination": "Jamaica"},
                ],
                "by_line": True,
            },
        ]
        connected = apply_exchange_wtc_subway_connections(path_board, subway_boards)
        self.assertEqual(EXCHANGE_WTC_PATH_WALK, 8)
        cortlandt = connected[0]
        wtc = connected[1]
        self.assertEqual(len(cortlandt["trains"]), 1)
        self.assertEqual(cortlandt["trains"][0]["minutes"], 19)
        self.assertIn("Exchange +8", cortlandt["note"])
        self.assertEqual(len(wtc["trains"]), 1)
        self.assertEqual(wtc["trains"][0]["minutes"], 22)

    def test_filters_subway_after_lsp_path_and_walk(self):
        lsp = {
            "label": "LSP",
            "trains": [{"minutes": 5, "destination": "Hoboken", "eta": "5m"}],
        }
        path_board = {
            "label": "Exchange Place",
            "trains": [
                {"destination": "WTC", "minutes": 10, "eta": "10m"},
                {"destination": "WTC", "minutes": 20, "eta": "20m"},
            ],
            "_raw_trains": [
                {"destination": "WTC", "minutes": 10, "eta": "10m"},
                {"destination": "WTC", "minutes": 20, "eta": "20m"},
            ],
        }
        subway_boards = [
            {
                "label": "WTC Cortlandt",
                "trains": [{"line": "1", "minutes": 30, "eta": "30m", "destination": "Van Cortlandt"}],
                "_raw_trains": [
                    {"line": "1", "minutes": 25, "eta": "25m", "destination": "Van Cortlandt"},
                    {"line": "1", "minutes": 30, "eta": "30m", "destination": "Van Cortlandt"},
                ],
                "by_line": True,
            },
        ]
        connected = apply_exchange_wtc_subway_connections(
            path_board, subway_boards, lsp_primary=lsp
        )
        cortlandt = connected[0]
        self.assertEqual(len(cortlandt["trains"]), 1)
        self.assertEqual(cortlandt["trains"][0]["minutes"], 30)
        self.assertIn("LSP HBLR +11", cortlandt["note"])
        self.assertIn("Exchange +8", cortlandt["note"])

    @mock.patch("lib.path_trains.get_path_transit_board", return_value=None)
    def test_lsp_blocks_too_early_exchange_path(self, _transit_mock):
        lsp = {
            "label": "LSP",
            "trains": [{"minutes": 5, "destination": "Hoboken", "eta": "5m"}],
        }
        path_board = {
            "label": "Exchange Place",
            "trains": [{"destination": "WTC", "minutes": 10, "eta": "10m"}],
            "_raw_trains": [{"destination": "WTC", "minutes": 10, "eta": "10m"}],
        }
        subway_boards = [
            {
                "label": "WTC",
                "trains": [{"line": "E", "minutes": 22, "eta": "22m", "destination": "Jamaica"}],
                "_raw_trains": [{"line": "E", "minutes": 22, "eta": "22m", "destination": "Jamaica"}],
                "by_line": True,
            },
        ]
        connected = apply_exchange_wtc_subway_connections(
            path_board, subway_boards, lsp_primary=lsp
        )
        self.assertEqual(connected[0]["trains"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
