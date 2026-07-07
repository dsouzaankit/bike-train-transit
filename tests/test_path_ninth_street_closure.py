# -*- coding: utf-8 -*-
"""PATH 9 St overnight closure (schedule + Everbridge overlay)."""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import path_trains  # noqa: E402
from lib.path_trains import (  # noqa: E402
    NINTH_STREET_CLOSED_NOTE,
    PATH_33RD_STATIONS,
    _board_from_payload,
    _is_nj_direction,
    _is_nyc_direction,
    _load_14th_path_board,
    get_path_station_board,
    ninth_street_closure,
)


def _ninth_station():
    return next(s for s in PATH_33RD_STATIONS if s["panynj"] == "09S")


class NinthStreetClosureTests(unittest.TestCase):
    def setUp(self):
        path_trains._EVERBRIDGE_CACHE["fetched_at"] = 0.0
        path_trains._EVERBRIDGE_CACHE["incidents"] = None

    def test_closed_overnight_window(self):
        closed, note = ninth_street_closure(
            now=datetime.datetime(2026, 7, 7, 1, 30)
        )
        self.assertTrue(closed)
        self.assertEqual(note, NINTH_STREET_CLOSED_NOTE)

    def test_open_midday(self):
        closed, note = ninth_street_closure(
            now=datetime.datetime(2026, 7, 7, 10, 0)
        )
        self.assertFalse(closed)
        self.assertIsNone(note)

    def test_open_before_1159pm(self):
        closed, _ = ninth_street_closure(now=datetime.datetime(2026, 7, 6, 23, 58))
        self.assertFalse(closed)

    def test_closed_after_1159pm(self):
        closed, _ = ninth_street_closure(now=datetime.datetime(2026, 7, 6, 23, 59))
        self.assertTrue(closed)

    def test_reopens_at_5am(self):
        closed, _ = ninth_street_closure(now=datetime.datetime(2026, 7, 7, 5, 0))
        self.assertFalse(closed)

    def test_board_from_payload_suppresses_panynj(self):
        payload = {
            "results": [
                {
                    "consideredStation": "09S",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "33rd Street",
                                    "arrivalTimeMessage": "3 min",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        board = _board_from_payload(
            _ninth_station(),
            payload,
            _is_nyc_direction,
            now=datetime.datetime(2026, 7, 7, 2, 0),
        )
        self.assertTrue(board.get("closed"))
        self.assertEqual(board["trains"], [])
        self.assertEqual(board.get("note"), NINTH_STREET_CLOSED_NOTE)

    def test_get_path_station_board_closed(self):
        board = get_path_station_board(
            "9 St",
            "nj",
            now=datetime.datetime(2026, 7, 7, 3, 15),
        )
        self.assertTrue(board.get("closed"))
        self.assertEqual(board["trains"], [])

    def test_14th_skips_ninth_fallback_when_closed(self):
        payload = {
            "results": [
                {
                    "consideredStation": "14S",
                    "destinations": [{"label": "ToNY", "messages": []}],
                },
                {
                    "consideredStation": "09S",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "33rd Street",
                                    "arrivalTimeMessage": "4 min",
                                }
                            ],
                        }
                    ],
                },
            ]
        }
        board = _load_14th_path_board(
            None,
            panynj_payload=payload,
            now=datetime.datetime(2026, 7, 7, 2, 0),
        )
        self.assertEqual(board["trains"], [])
        self.assertNotIn("est. 9 St", board.get("note") or "")

    def test_everbridge_extends_closure_past_schedule(self):
        def fetch_json(url):
            if "everbridge" in url:
                return {
                    "data": [
                        {
                            "title": "9 St Station and 23 St Station Overnight Advisory",
                            "message": "stations close every night until further notice",
                        }
                    ]
                }
            raise AssertionError("unexpected url %s" % url)

        closed, note = ninth_street_closure(
            fetch_json=fetch_json,
            now=datetime.datetime(2026, 7, 7, 12, 0),
        )
        self.assertTrue(closed)
        self.assertEqual(note, NINTH_STREET_CLOSED_NOTE)

    def test_open_daytime_without_everbridge_match(self):
        def fetch_json(url):
            if "everbridge" in url:
                return {"data": [{"title": "Newport elevator out of service"}]}
            raise AssertionError(url)

        closed, _ = ninth_street_closure(
            fetch_json=fetch_json,
            now=datetime.datetime(2026, 7, 7, 12, 0),
        )
        self.assertFalse(closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
