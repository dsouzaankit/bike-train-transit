# -*- coding: utf-8 -*-
"""Unit tests for MT→JC chained transfer offsets."""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.hblr_path import apply_transfer_filter  # noqa: E402
from lib.mt_to_jc import (  # noqa: E402
    MT_SUBWAY_SOURCES,
    MT_TO_JC_ROWS,
    _chain_hblr_from_path,
    build_mt_to_jc_rows,
    f_line_active,
)


def _board(label, minutes, raw=None, **extra):
    board = {
        "label": label,
        "trains": [
            {"minutes": m, "destination": "JSQ", "eta": "%dm" % m, "line": "E"}
            for m in minutes
        ],
        "error": None,
    }
    if raw is not None:
        board["_raw_trains"] = board["trains"]
    board.update(extra)
    return board


def _mins(board):
    return [t["minutes"] for t in board.get("trains") or []]


class MtToJcChainTests(unittest.TestCase):
    def test_path_from_subway_row1(self):
        cfg = MT_TO_JC_ROWS[0]
        subway = _board("50 St (8Av)", [10])
        path = _board("9 St", [20, 30, 40], raw=[20, 30, 40])
        out = apply_transfer_filter(
            subway, path, cfg["path_primary"]["offset"], "50 St (8Av)", "9 St"
        )
        self.assertEqual(_mins(out), [30, 40])
        self.assertEqual(out["note"], "50 St (8Av) +15")

    def test_hblr_newport_from_9th_path(self):
        cfg = MT_TO_JC_ROWS[0]
        path = _board("9 St", [20])
        hblr = _board("Newport HBLR", [30, 35, 40], raw=[30, 35, 40])
        out = apply_transfer_filter(
            path, hblr, cfg["hblr_newport_offset"], "9 St", "Newport HBLR"
        )
        self.assertEqual(_mins(out), [35, 40])

    def test_hblr_exchange_from_wtc_path(self):
        cfg = MT_TO_JC_ROWS[1]
        path = _board("WTC", [12])
        hblr = _board("Exchange HBLR", [15, 20, 25], raw=[15, 20, 25])
        out = apply_transfer_filter(
            path, hblr, cfg["hblr_exchange_offset"], "WTC", "Exchange HBLR"
        )
        self.assertEqual(_mins(out), [20, 25])

    def test_f_line_weekday_window(self):
        wed_morning = datetime.datetime(2026, 7, 8, 8, 0)
        wed_night = datetime.datetime(2026, 7, 8, 22, 0)
        saturday = datetime.datetime(2026, 7, 11, 12, 0)
        self.assertTrue(f_line_active(wed_morning))
        self.assertFalse(f_line_active(wed_night))
        self.assertFalse(f_line_active(saturday))

    def test_hblr_no_current_fallback_when_not_catchable(self):
        path = _board("9 St", [20])
        hblr = _board(
            "Newport HBLR",
            [3, 5, 8],
            raw=[3, 5, 8],
            source="transit",
        )
        out = _chain_hblr_from_path(path, hblr, 14, "9 St", "Newport HBLR")
        self.assertEqual(_mins(out), [])
        self.assertNotIn("current HBLR", out.get("note") or "")

    def test_50_8av_wtc_offset(self):
        cfg = MT_TO_JC_ROWS[0]
        self.assertEqual(cfg["subway_key"], "50_8av")
        self.assertEqual(cfg["path_wtc_offset"], 19)

    def test_50_st_platforms_differ(self):
        self.assertEqual(
            MT_SUBWAY_SOURCES["50_8av"]["stations"][0]["station_id"],
            "A25",
        )
        self.assertEqual(
            MT_SUBWAY_SOURCES["50_7av"]["stations"][0]["station_id"],
            "125",
        )
        self.assertIn("E", [line for line, _dir in MT_SUBWAY_SOURCES["50_8av"]["line_specs"]])
        self.assertIn("1", [line for line, _dir in MT_SUBWAY_SOURCES["50_7av"]["line_specs"]])

    def test_build_rows_offline_shape(self):
        rows = build_mt_to_jc_rows({}, fetch_json=None)
        self.assertEqual(len(rows), 3)
        for row in rows:
            for key in (
                "subway",
                "path_primary",
                "path_wtc",
                "hblr_newport",
                "hblr_exchange",
            ):
                self.assertIn(key, row)
                self.assertIn("label", row[key])


    def test_ninth_street_transit_stop(self):
        from lib.path_trains import PATH_NINTH_TRANSIT_STOP, PATH_NJ_STATIONS

        ninth = next(s for s in PATH_NJ_STATIONS if s["panynj"] == "09S")
        self.assertEqual(ninth.get("transit_stop_id"), PATH_NINTH_TRANSIT_STOP)

    def test_mt_jc_path_includes_hoboken(self):
        from lib.path_trains import (
            _is_mt_to_jc_path_destination,
            _is_nwk_jsq_destination,
            _parse_panynj_station,
            _is_nj_direction,
        )

        self.assertTrue(_is_nwk_jsq_destination("Journal Square"))
        self.assertFalse(_is_nwk_jsq_destination("Hoboken"))
        self.assertTrue(_is_mt_to_jc_path_destination("Hoboken"))
        self.assertTrue(_is_mt_to_jc_path_destination("Newark"))
        self.assertFalse(_is_mt_to_jc_path_destination("33rd Street via Hoboken"))
        self.assertFalse(_is_mt_to_jc_path_destination("World Trade Center"))

        payload = {
            "results": [
                {
                    "consideredStation": "09S",
                    "destinations": [
                        {
                            "label": "ToNJ",
                            "messages": [
                                {
                                    "headSign": "Hoboken",
                                    "arrivalTimeMessage": "8 min",
                                },
                                {
                                    "headSign": "33rd Street",
                                    "arrivalTimeMessage": "3 min",
                                },
                            ],
                        }
                    ],
                }
            ]
        }
        trains = _parse_panynj_station(
            "09S",
            payload,
            _is_nj_direction,
            dest_filter=_is_mt_to_jc_path_destination,
            allow_hoboken=True,
        )
        self.assertEqual([t["destination"] for t in trains], ["Hoboken"])


if __name__ == "__main__":
    unittest.main()
