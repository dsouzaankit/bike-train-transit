# -*- coding: utf-8 -*-
"""Exchange Place PATH → WTC + northbound subway connection (From JC)."""

import os
import sys
import unittest

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
        self.assertIn("after Exchange +8", cortlandt["note"])
        self.assertEqual(len(wtc["trains"]), 1)
        self.assertEqual(wtc["trains"][0]["minutes"], 22)


if __name__ == "__main__":
    unittest.main(verbosity=2)
