# -*- coding: utf-8 -*-
"""PATH destination shortening for compact HBLR-tab cards."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.path_trains import (  # noqa: E402
    _is_nyc_direction,
    _is_wtc_destination,
    _parse_panynj_station,
    _short_destination,
)


class PathDestinationShortTests(unittest.TestCase):
    def test_wtc_variants(self):
        self.assertEqual(_short_destination("World Trade Center"), "WTC")
        self.assertEqual(_short_destination("To World Trade Center"), "WTC")

    def test_33rd_variants(self):
        self.assertEqual(_short_destination("33rd Street"), "33rd St")
        self.assertEqual(_short_destination("33rd Street via Hoboken"), "33rd via Hob")
        self.assertEqual(_short_destination("Journal Square via Hoboken"), "JSQ via Hob")

    def test_journal_square_33rd_combo(self):
        self.assertEqual(_short_destination("Journal Square-33rd Street"), "33rd St")

    def test_wtc_filter_accepts_tuple_headsign(self):
        self.assertTrue(_is_wtc_destination(("World Trade Center",)))

    def test_parse_panynj_tuple_headsign(self):
        payload = {
            "results": [
                {
                    "consideredStation": "EXCH",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": ("World Trade Center",),
                                    "arrivalTimeMessage": "5 min",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        trains = _parse_panynj_station(
            "EXCH",
            payload,
            _is_nyc_direction,
            dest_filter=_is_wtc_destination,
        )
        self.assertEqual(len(trains), 1)
        self.assertEqual(trains[0]["destination"], "WTC")


if __name__ == "__main__":
    unittest.main(verbosity=2)
