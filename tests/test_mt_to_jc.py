# -*- coding: utf-8 -*-
"""Unit tests for MT→JC chained transfer offsets."""

import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.hblr_path import apply_transfer_filter  # noqa: E402
from lib.mt_to_jc import (  # noqa: E402
    MT_DOWNTOWN_GATES,
    MT_SUBWAY_SOURCES,
    MT_TO_JC_ROWS,
    _chain_hblr_from_path,
    _gate_on_subway,
    _gate_path_on_downtown,
    _load_mt_subway_board,
    build_mt_to_jc_rows,
    f_line_active,
)
from lib.subway_trains import (  # noqa: E402
    SUBWAY_CHRIS_SOUTH,
    SUBWAY_FIFTY_ST_7AV_SOUTH,
    SUBWAY_FIFTY_ST_8AV_SOUTH,
    SUBWAY_LEX_53_SOUTH,
    SUBWAY_WEST_4_SOUTH,
    SUBWAY_WTC_CORTLANDT,
    SUBWAY_WTC_E,
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
    def test_path_from_subway_50_8av(self):
        cfg = MT_TO_JC_ROWS[0]
        subway = _board("50 St (8Av)", [20])
        path = _board("9 St", [20, 30, 40], raw=[20, 30, 40])
        out = apply_transfer_filter(
            subway, path, cfg["path_primary"]["offset"], "50 St (8Av)", "9 St"
        )
        self.assertEqual(_mins(out), [40])
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

    def test_f_note_only_when_f_filtered(self):
        from lib.mt_to_jc import _load_subway_source

        night = datetime.datetime(2026, 7, 8, 2, 0)

        def fetch_e_only(station, fetch_json, **kwargs):
            return [
                {
                    "line": "E",
                    "direction": "S",
                    "destination": "WTC",
                    "minutes": 8,
                    "eta": "8m",
                }
            ]

        with mock.patch(
            "lib.subway_trains.fetch_station_arrivals", side_effect=fetch_e_only
        ):
            board = _load_subway_source(
                "50_8av", MT_SUBWAY_SOURCES, fetch_json=lambda u: {}, now=night
            )
        self.assertEqual(len(board.get("trains") or []), 1)
        self.assertNotIn("F wkdys", board.get("note") or "")

        def fetch_with_f(station, fetch_json, **kwargs):
            return [
                {
                    "line": "F",
                    "direction": "S",
                    "destination": "Coney Island",
                    "minutes": 5,
                    "eta": "5m",
                },
                {
                    "line": "E",
                    "direction": "S",
                    "destination": "WTC",
                    "minutes": 8,
                    "eta": "8m",
                },
            ]

        with mock.patch(
            "lib.subway_trains.fetch_station_arrivals", side_effect=fetch_with_f
        ):
            board = _load_subway_source(
                "50_8av", MT_SUBWAY_SOURCES, fetch_json=lambda u: {}, now=night
            )
        self.assertIn("F wkdys", board.get("note") or "")

    def test_f_line_weekday_window(self):
        wed_morning = datetime.datetime(2026, 7, 8, 8, 0)
        wed_night = datetime.datetime(2026, 7, 8, 22, 0)
        saturday = datetime.datetime(2026, 7, 11, 12, 0)
        self.assertTrue(f_line_active(wed_morning))
        self.assertFalse(f_line_active(wed_night))
        self.assertFalse(f_line_active(saturday))

    def test_shuttle_rows_never_f_note(self):
        board = _load_mt_subway_board("50_st_2", fetch_json=None)
        self.assertNotIn("F wkdys", board.get("note") or "")
        board = _load_mt_subway_board("50_st_ac", fetch_json=None)
        self.assertNotIn("F wkdys", board.get("note") or "")

    def test_hblr_no_current_fallback_when_not_catchable(self):
        subway = _board("Chris St", [5])
        path = _board("9 St", [20])
        hblr = _board(
            "Newport HBLR",
            [3, 5, 8],
            raw=[3, 5, 8],
            source="transit",
        )
        out = _chain_hblr_from_path(
            subway, path, hblr, 14, "9 St", "Newport HBLR"
        )
        self.assertEqual(_mins(out), [])
        self.assertNotIn("current HBLR", out.get("note") or "")

    def test_50_8av_row_offsets(self):
        cfg = MT_TO_JC_ROWS[0]
        self.assertEqual(cfg["subway_key"], "50_8av")
        self.assertEqual(cfg["path_wtc_offset"], 19)
        self.assertEqual(cfg["path_primary"]["station"], "9 St")

    def test_row_and_downtown_sources(self):
        self.assertEqual(MT_SUBWAY_SOURCES["50_8av"]["station"], SUBWAY_FIFTY_ST_8AV_SOUTH)
        self.assertEqual(MT_SUBWAY_SOURCES["50_7av"]["station"], SUBWAY_FIFTY_ST_7AV_SOUTH)
        self.assertEqual(MT_SUBWAY_SOURCES["lex_53"]["station"], SUBWAY_LEX_53_SOUTH)
        self.assertEqual(MT_DOWNTOWN_GATES["wtc_e"]["station"], SUBWAY_WTC_E)
        self.assertEqual(MT_DOWNTOWN_GATES["wtc_cortlandt"]["station"], SUBWAY_WTC_CORTLANDT)
        self.assertEqual(MT_DOWNTOWN_GATES["west_4"]["station"], SUBWAY_WEST_4_SOUTH)
        self.assertEqual(MT_DOWNTOWN_GATES["chris_st"]["station"], SUBWAY_CHRIS_SOUTH)

    def test_build_rows_offline_shape(self):
        rows = build_mt_to_jc_rows({}, fetch_json=None)
        self.assertEqual(len(rows), 5)
        for row in rows:
            for key in ("subway", "path_primary", "hblr_newport"):
                self.assertIn(key, row)
                self.assertIn("label", row[key])
            if row["id"] in ("mt_50_st_2", "mt_50_st_ac"):
                self.assertIsNone(row.get("path_wtc"))
                self.assertIsNone(row.get("hblr_exchange"))
            else:
                self.assertIsNotNone(row.get("path_wtc"))
                self.assertIsNotNone(row.get("hblr_exchange"))

    def test_50_st_2_row_no_wtc(self):
        cfg = next(row for row in MT_TO_JC_ROWS if row["id"] == "mt_50_st_2")
        self.assertFalse(cfg.get("include_wtc_path", True))
        self.assertEqual(cfg["path_primary"]["station"], "Chris St")

    def test_downtown_gate_clears_path(self):
        path = _board("9 St", [20, 30])
        downtown = {
            "west_4": {"label": "West 4 St", "trains": []},
        }
        out = _gate_path_on_downtown(path, "9 St", "mt_50_8av", downtown)
        self.assertEqual(_mins(out), [])
        self.assertIn("no West 4 St southbound", out["note"])

    def test_downtown_gate_lex_wtc_e_only(self):
        path = _board("WTC", [12])
        downtown = {
            "wtc_e": {"label": "WTC", "trains": []},
            "wtc_cortlandt": {"label": "WTC Cortlandt", "trains": [{"minutes": 5}]},
        }
        out = _gate_path_on_downtown(path, "WTC", "mt_lex_53", downtown)
        self.assertEqual(_mins(out), [])
        self.assertIn("no WTC southbound", out["note"])

    def test_subway_unavailable_gates_path(self):
        subway = {"label": "50 St (8Av)", "trains": [], "unavailable": True}
        path = _board("WTC", [5, 10], raw=[5, 10])
        gated = _gate_on_subway(subway, path, "WTC")
        self.assertEqual(gated["trains"], [])
        self.assertIn("no 50 St (8Av) yet", gated["note"])

    def test_offline_subway_marks_unavailable(self):
        board = _load_mt_subway_board("50_8av", fetch_json=None)
        self.assertTrue(board.get("unavailable"))

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
    unittest.main(verbosity=2)
