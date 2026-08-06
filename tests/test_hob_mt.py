# -*- coding: utf-8 -*-
"""Unit tests for HOB↔MT section offsets and layout."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.hblr_path import apply_transfer_filter  # noqa: E402
from lib.hob_mt import (  # noqa: E402
    F_INACTIVE_NOTE,
    HOB_MT_F_EXTRA,
    HOB_MT_GC_FROM_SEVEN_OFFSET,
    HOB_MT_MTA_BUS_OFFSET,
    HOB_MT_PABT_EC_OFFSET,
    HOB_MT_SECTION_TITLES,
    HOB_MT_SEVEN_EXTRA,
    HOB_MT_WALK_OFFSET,
    SECTION_FERRY_BUS,
    SECTION_HOB_TERMINAL,
    SECTION_NJT_PABT,
    SECTION_SUBWAY,
    _catchable_primary_board,
    _is_nyc_bus_headsign,
    _is_pabt_departure_headsign,
    build_hob_mt_sections,
    extract_lincoln_nyc_minutes,
    f_transfer_offset,
    gc_from_seven_offset,
    pabt_ec_transfer_offset,
    resolve_lincoln_nyc_minutes,
    subway_base_offset,
    seven_transfer_offset,
)


def _board(label, minutes, **extra):
    board = {
        "label": label,
        "trains": [
            {
                "minutes": m,
                "destination": "dest",
                "eta": "%dm" % m,
                "line": "E",
            }
            for m in minutes
        ],
        "error": None,
        "_raw_trains": [
            {
                "minutes": m,
                "destination": "dest",
                "eta": "%dm" % m,
                "line": "E",
            }
            for m in minutes
        ],
        "source": "subwayapi",
    }
    board.update(extra)
    return board


def _mins(board):
    return [t["minutes"] for t in board.get("trains") or []]


class LincolnOffsetTests(unittest.TestCase):
    def test_extract_lincoln_nyc_minutes(self):
        boards = [
            {
                "label": "Lincoln Tunnel",
                "trains": [
                    {"destination": "→ NYC", "minutes": 12},
                    {"destination": "→ NJ", "minutes": 8},
                ],
            },
            {
                "label": "Holland Tunnel",
                "trains": [{"destination": "→ NYC", "minutes": 20}],
            },
        ]
        self.assertEqual(extract_lincoln_nyc_minutes(boards), 12)

    def test_extract_lincoln_missing_returns_none(self):
        self.assertIsNone(extract_lincoln_nyc_minutes([]))
        self.assertIsNone(
            extract_lincoln_nyc_minutes(
                [{"label": "Lincoln Tunnel", "trains": [{"destination": "→ NYC", "minutes": None}]}]
            )
        )

    def test_subway_base_offset(self):
        # Walk after LincTnl only; Lincoln minutes live on the primary board.
        self.assertEqual(subway_base_offset(10), HOB_MT_WALK_OFFSET)
        self.assertEqual(subway_base_offset(None), HOB_MT_WALK_OFFSET)
        self.assertEqual(subway_base_offset(0), HOB_MT_WALK_OFFSET)

    def test_resolve_lincoln_uses_transit_payload_when_cache_empty(self):
        cached = []
        payload = [
            {
                "crossingDisplayName": "Lincoln Tunnel",
                "travelDirection": "ToNY",
                "timeStatusMessage": "9",
                "isDataAvailable": True,
            }
        ]

        def fetch_payload(_url):
            return payload

        self.assertIsNone(resolve_lincoln_nyc_minutes(tunnel_boards_cached=cached))
        self.assertEqual(
            resolve_lincoln_nyc_minutes(
                tunnel_boards_cached=cached,
                fetch_transit_payload=fetch_payload,
            ),
            9,
        )


class TransferOffsetTests(unittest.TestCase):
    def test_seven_and_f_extras(self):
        base = subway_base_offset()
        self.assertEqual(base, HOB_MT_WALK_OFFSET)
        self.assertEqual(pabt_ec_transfer_offset(), HOB_MT_PABT_EC_OFFSET)
        self.assertEqual(pabt_ec_transfer_offset(), 3)
        self.assertEqual(seven_transfer_offset(base), base + HOB_MT_SEVEN_EXTRA)
        self.assertEqual(f_transfer_offset(base), base + HOB_MT_F_EXTRA)
        self.assertEqual(seven_transfer_offset(base), 6)
        self.assertEqual(f_transfer_offset(base), 9)
        self.assertEqual(gc_from_seven_offset(), HOB_MT_GC_FROM_SEVEN_OFFSET)
        self.assertEqual(gc_from_seven_offset(), 3)

    def test_seven_filter_uses_linctnl_plus_six(self):
        lincoln = _board("LincTnl → NYC", [10], source="panynj-crossingtimes")
        seven = _board("7", [12, 15, 18, 22])
        out = apply_transfer_filter(
            lincoln, seven, seven_transfer_offset(subway_base_offset()), "LincTnl", "7"
        )
        # threshold = 10 + 6 → keep >= 16
        self.assertEqual(_mins(out), [18, 22])
        self.assertEqual(out.get("note"), "LincTnl +6")

    def test_f_filter_uses_linctnl_plus_nine(self):
        lincoln = _board("LincTnl → NYC", [10], source="panynj-crossingtimes")
        f_board = _board("F", [15, 18, 22, 30], line="F")
        out = apply_transfer_filter(
            lincoln, f_board, f_transfer_offset(subway_base_offset()), "LincTnl", "F"
        )
        # threshold = 10 + 9 → keep >= 19
        self.assertEqual(_mins(out), [22, 30])
        self.assertEqual(out.get("note"), "LincTnl +9")

    def test_gc_chains_from_first_catchable_seven_plus_three(self):
        lincoln = _board("LincTnl → NYC", [10], source="panynj-crossingtimes")
        seven = _board("7", [12, 15, 18, 22])
        seven_out = apply_transfer_filter(
            lincoln, seven, seven_transfer_offset(subway_base_offset()), "LincTnl", "7"
        )
        # first catchable 7 = 18; GC threshold = 18 + 3
        self.assertEqual(_mins(seven_out)[0], 18)
        six = _board("6", [18, 20, 22, 25, 40])
        out = apply_transfer_filter(
            _catchable_primary_board(seven_out, "7"),
            six,
            gc_from_seven_offset(),
            "7",
            "6",
        )
        self.assertEqual(_mins(out), [22, 25, 40])
        self.assertEqual(out.get("note"), "7 +3")

    def test_gc_skips_seven_current_fallback(self):
        seven_fallback = _board("7", [5, 8], note="LincTnl +6 · current subway")
        primary = _catchable_primary_board(seven_fallback, "7")
        self.assertEqual(primary.get("trains"), [])
        six = _board("6", [10, 20])
        out = apply_transfer_filter(primary, six, gc_from_seven_offset(), "7", "6")
        self.assertEqual(out.get("note"), "no 7 yet")

    def test_pabt_ec_filter_note_is_linctnl_plus_three(self):
        lincoln = _board("LincTnl → NYC", [12], source="panynj-crossingtimes")
        subway = _board("42 St-PABT", [10, 14, 16, 20])
        out = apply_transfer_filter(
            lincoln, subway, pabt_ec_transfer_offset(), "LincTnl", "42 St-PABT"
        )
        # threshold = 12 + 3
        self.assertEqual(_mins(out), [16, 20])
        self.assertEqual(out.get("note"), "LincTnl +3")

    def test_walk_base_offset_is_four(self):
        """HOB_MT_WALK_OFFSET still derives F (+9) / 7 (+6); not used on 50/51/33."""
        lincoln = _board("LincTnl → NYC", [12], source="panynj-crossingtimes")
        subway = _board("secondary", [10, 14, 16, 20])
        out = apply_transfer_filter(
            lincoln, subway, subway_base_offset(), "LincTnl", "secondary"
        )
        # threshold = 12 + 4
        self.assertEqual(_mins(out), [16, 20])
        self.assertEqual(out.get("note"), "LincTnl +4")

    def test_empty_catchable_hint_lists_lines(self):
        lincoln = _board("LincTnl → NYC", [20], source="panynj-crossingtimes")
        subway = _board(
            "42 St-PABT",
            [5, 8],
            _line_specs=(("E", "N"), ("A", "N")),
            source="subwayapi",
        )
        out = apply_transfer_filter(
            lincoln, subway, pabt_ec_transfer_offset(), "LincTnl", "42 St-PABT"
        )
        self.assertEqual(_mins(out), [])
        self.assertEqual(out.get("empty_hint"), "None catchable · A/E")

    def test_f_inactive_note_constant(self):
        self.assertEqual(F_INACTIVE_NOTE, "F wkdys 6a–9:30p")

    def test_mta_offset_is_fifteen(self):
        self.assertEqual(HOB_MT_MTA_BUS_OFFSET, 15)
        now = _board("now", [0], source="synthetic")
        buses = _board("12 Av", [10, 14, 15, 20, 30], source="transit")
        out = apply_transfer_filter(
            now,
            buses,
            HOB_MT_MTA_BUS_OFFSET,
            "now",
            "12 Av",
            fallback_current=True,
            fallback_suffix="bus",
        )
        self.assertEqual(_mins(out), [15, 20, 30])


class SectionOrderTests(unittest.TestCase):
    def test_section_titles_constant_order(self):
        self.assertEqual(
            list(HOB_MT_SECTION_TITLES),
            [
                SECTION_HOB_TERMINAL,
                SECTION_NJT_PABT,
                SECTION_SUBWAY,
                SECTION_FERRY_BUS,
            ],
        )

    def test_pabt_keeps_departures_not_nyc_bound(self):
        self.assertTrue(_is_pabt_departure_headsign("Hoboken-PATH"))
        self.assertTrue(_is_pabt_departure_headsign("Jersey City Bayonne"))
        self.assertFalse(_is_pabt_departure_headsign("New York"))
        self.assertFalse(_is_pabt_departure_headsign("New York via Clinton"))

    def test_hoboken_126_keeps_nyc_bound(self):
        self.assertTrue(_is_nyc_bus_headsign("New York"))
        self.assertTrue(_is_nyc_bus_headsign("New York via Clinton"))
        self.assertFalse(_is_nyc_bus_headsign("Journal Square"))

    def test_hoboken_hblr_keeps_tonnelle_only(self):
        from lib.hob_mt import fetch_hoboken_hblr_tonnelle_board

        with mock.patch(
            "lib.light_rail.get_hblr_board",
            return_value={
                "label": "Hoboken HBLR",
                "trains": [
                    {"destination": "Tonnelle Av", "minutes": 3, "eta": "3m"},
                    {"destination": "8th St", "minutes": 5, "eta": "5m"},
                ],
                "_raw_trains": [
                    {"destination": "Tonnelle Av", "minutes": 3, "eta": "3m"},
                    {"destination": "8th St", "minutes": 5, "eta": "5m"},
                    {"destination": "Tonnelle Avenue", "minutes": 12, "eta": "12m"},
                ],
                "error": None,
                "source": "transit",
            },
        ):
            board = fetch_hoboken_hblr_tonnelle_board()
        dests = [t["destination"] for t in board["trains"]]
        self.assertEqual(dests, ["Tonnelle Av", "Tonnelle Avenue"])
        self.assertEqual(board["label"], "Hoboken HBLR")

    def test_build_sections_title_order(self):
        def fetch_json(_url):
            raise RuntimeError("network disabled")

        with mock.patch("lib.hob_mt.get_tunnel_boards", return_value=[]), mock.patch(
            "lib.hob_mt.fetch_hoboken_126_board",
            return_value={"label": "Hoboken Terminal", "trains": [], "error": None},
        ), mock.patch(
            "lib.hob_mt.fetch_hoboken_hblr_tonnelle_board",
            return_value={"label": "Hoboken HBLR", "trains": [], "error": None},
        ), mock.patch(
            "lib.hob_mt.fetch_njt_willow_board",
            return_value={"label": "Willow Ave + 15th St", "trains": [], "error": None},
        ), mock.patch(
            "lib.hob_mt.fetch_pabt_board",
            return_value={"label": "PABT dep", "trains": [], "error": None},
        ), mock.patch(
            "lib.hob_mt.build_subway_catchable_boards",
            return_value=[{"label": "Lincoln → NYC", "trains": [{"minutes": 0}]}],
        ), mock.patch(
            "lib.hob_mt.fetch_nywaterway_board",
            return_value={"label": "Hoboken 14th St", "trains": [], "note": "see eta/9"},
        ), mock.patch(
            "lib.hob_mt.fetch_mta_bus_board",
            return_value={
                "label": "12 Av / W 42 St",
                "trains": [],
                "error": None,
                "_raw_trains": [],
                "source": "transit",
            },
        ):
            sections = build_hob_mt_sections(fetch_json)

        titles = [s["title"] for s in sections]
        self.assertEqual(titles, list(HOB_MT_SECTION_TITLES))
        self.assertEqual(sections[0]["title"], SECTION_HOB_TERMINAL)
        self.assertEqual(len(sections[0]["boards"]), 2)
        self.assertEqual(len(sections[1]["boards"]), 2)
        self.assertEqual(len(sections[-1]["boards"]), 2)
        for section in sections:
            self.assertIn("boards", section)
            self.assertIsInstance(section["boards"], list)


class SubwayCatchableBoardTests(unittest.TestCase):
    def test_f_card_inactive_outside_weekday_window(self):
        from lib.hob_mt import build_subway_catchable_boards

        def fetch_json(_url):
            raise RuntimeError("network disabled")

        with mock.patch("lib.hob_mt.f_line_active", return_value=False), mock.patch(
            "lib.hob_mt._load_line_board",
            side_effect=RuntimeError("skip"),
        ), mock.patch(
            "lib.hob_mt._load_express_local_board",
            side_effect=RuntimeError("skip"),
        ), mock.patch(
            "lib.hob_mt._load_grand_central_6_board",
            side_effect=RuntimeError("skip"),
        ):
            boards = build_subway_catchable_boards(fetch_json, lincoln_nyc_minutes=10)

        labels = [b.get("label") for b in boards]
        self.assertEqual(labels[0], "LincTnl → NYC")
        self.assertEqual(labels[1], "42 St-PABT")
        self.assertEqual(labels[2], "42 St-Bryant Pk (F)")
        self.assertEqual(boards[2].get("note"), F_INACTIVE_NOTE)
        self.assertEqual(boards[2].get("trains"), [])

    def test_f_card_active_uses_linctnl_plus_nine(self):
        from lib.hob_mt import build_subway_catchable_boards

        lincoln_trains = [{"minutes": 10, "eta": "10m", "destination": "→ NYC"}]
        f_raw = {
            "label": "42 St-Bryant Pk (F)",
            "trains": [
                {
                    "minutes": m,
                    "eta": "%dm" % m,
                    "destination": "Jamaica",
                    "line": "F",
                    "direction": "N",
                }
                for m in (15, 22, 30)
            ],
            "_raw_trains": [
                {
                    "minutes": m,
                    "eta": "%dm" % m,
                    "destination": "Jamaica",
                    "line": "F",
                    "direction": "N",
                }
                for m in (15, 22, 30)
            ],
            "source": "subwayapi",
            "error": None,
            "_line_specs": (("F", "N"),),
        }
        seven_raw = {
            "label": "Times Sq-42 St (7)",
            "trains": [
                {
                    "minutes": m,
                    "eta": "%dm" % m,
                    "destination": "Flushing",
                    "line": "7",
                    "direction": "N",
                }
                for m in (12, 18, 25)
            ],
            "_raw_trains": [
                {
                    "minutes": m,
                    "eta": "%dm" % m,
                    "destination": "Flushing",
                    "line": "7",
                    "direction": "N",
                }
                for m in (12, 18, 25)
            ],
            "source": "subwayapi",
            "error": None,
            "_line_specs": (("7", "N"),),
        }
        six_raw = {
            "label": "Grand Central-42 St",
            "trains": [
                {
                    "minutes": m,
                    "eta": "%dm" % m,
                    "destination": "Parkchester",
                    "line": "6",
                    "direction": "N",
                }
                for m in (18, 22, 30)
            ],
            "_raw_trains": [
                {
                    "minutes": m,
                    "eta": "%dm" % m,
                    "destination": "Parkchester",
                    "line": "6",
                    "direction": "N",
                }
                for m in (18, 22, 30)
            ],
            "source": "subwayapi",
            "error": None,
            "_line_specs": (("6", "N"), ("6", "S")),
        }

        def fake_line_board(station, *_args, **_kwargs):
            label = (station or {}).get("label") or ""
            if "Bryant" in label or (station or {}).get("station_id") == "D16":
                return dict(f_raw)
            if "Times Sq" in label or (station or {}).get("station_id") == "725":
                return dict(seven_raw)
            if "PABT" in label:
                return {
                    "label": "42 St-PABT",
                    "trains": [],
                    "_raw_trains": [],
                    "source": "subwayapi",
                    "error": None,
                }
            if "33 St" in label:
                return {
                    "label": "33 St",
                    "trains": [],
                    "_raw_trains": [],
                    "source": "subwayapi",
                    "error": None,
                }
            return {"label": label or "?", "trains": [], "_raw_trains": [], "error": None}

        with mock.patch("lib.hob_mt.f_line_active", return_value=True), mock.patch(
            "lib.hob_mt._load_line_board", side_effect=fake_line_board
        ), mock.patch(
            "lib.hob_mt._load_express_local_board",
            return_value={
                "label": "50 St",
                "trains": [],
                "_raw_trains": [],
                "source": "subwayapi",
                "error": None,
            },
        ), mock.patch(
            "lib.hob_mt._load_grand_central_6_board", return_value=dict(six_raw)
        ):
            boards = build_subway_catchable_boards(lambda _u: None, lincoln_nyc_minutes=10)

        by_label = {b["label"]: b for b in boards}
        self.assertEqual(by_label["42 St-Bryant Pk (F)"].get("note"), "LincTnl +9")
        self.assertEqual(_mins(by_label["42 St-Bryant Pk (F)"]), [22, 30])
        self.assertEqual(by_label["Times Sq-42 St (7)"].get("note"), "LincTnl +6")
        # threshold 10+6=16 → catchable 18, 25; first catchable 18
        self.assertEqual(_mins(by_label["Times Sq-42 St (7)"]), [18, 25])
        self.assertEqual(by_label["Grand Central-42 St"].get("note"), "7 +3")
        # first catchable 7 = 18 → threshold 21 → keep 22, 30
        self.assertEqual(_mins(by_label["Grand Central-42 St"]), [22, 30])

    def test_lex_and_50_st_are_current_not_linctnl_catchable(self):
        """50 / 51 / 33 St are not walkable from PABT — no LincTnl offset note."""
        from lib.hob_mt import build_subway_catchable_boards

        fifty = {
            "label": "50 St",
            "trains": [
                {
                    "minutes": 5,
                    "eta": "5m",
                    "destination": "Inwood",
                    "line": "A",
                    "direction": "N",
                }
            ],
            "_raw_trains": [],
            "source": "subwayapi",
            "error": None,
            "note": "Express local stop",
        }
        fifty_first = {
            "label": "51 St",
            "trains": [
                {
                    "minutes": 8,
                    "eta": "8m",
                    "destination": "Woodlawn",
                    "line": "4",
                    "direction": "N",
                }
            ],
            "_raw_trains": [],
            "source": "subwayapi",
            "error": None,
            "note": "Express local stop",
        }
        thirty_third = {
            "label": "33 St",
            "trains": [
                {
                    "minutes": 3,
                    "eta": "3m",
                    "destination": "Bk Bridge",
                    "line": "6",
                    "direction": "S",
                }
            ],
            "_raw_trains": [],
            "source": "subwayapi",
            "error": None,
        }

        def fake_line_board(station, *_args, **_kwargs):
            label = (station or {}).get("label") or ""
            if "33 St" in label:
                return dict(thirty_third)
            return {
                "label": label or "?",
                "trains": [],
                "_raw_trains": [],
                "source": "subwayapi",
                "error": None,
            }

        def fake_express(station, *_args, **_kwargs):
            label = (station or {}).get("label") or ""
            if "50 St" in label:
                return dict(fifty)
            if "51 St" in label:
                return dict(fifty_first)
            return {"label": label or "?", "trains": [], "_raw_trains": [], "error": None}

        with mock.patch("lib.hob_mt.f_line_active", return_value=False), mock.patch(
            "lib.hob_mt._load_line_board", side_effect=fake_line_board
        ), mock.patch(
            "lib.hob_mt._load_express_local_board", side_effect=fake_express
        ), mock.patch(
            "lib.hob_mt._load_grand_central_6_board",
            return_value={"label": "Grand Central-42 St", "trains": [], "error": None},
        ):
            boards = build_subway_catchable_boards(lambda _u: None, lincoln_nyc_minutes=10)

        by_label = {b["label"]: b for b in boards}
        for label in ("50 St", "51 St", "33 St"):
            note = by_label[label].get("note") or ""
            self.assertNotIn("LincTnl", note, label)
        self.assertEqual(_mins(by_label["50 St"]), [5])
        self.assertEqual(_mins(by_label["51 St"]), [8])
        self.assertEqual(_mins(by_label["33 St"]), [3])
        # Express-local annotation may remain; must not be replaced by LincTnl +N.
        self.assertEqual(by_label["50 St"].get("note"), "Express local stop")
        self.assertEqual(by_label["51 St"].get("note"), "Express local stop")


if __name__ == "__main__":
    unittest.main(verbosity=2)
