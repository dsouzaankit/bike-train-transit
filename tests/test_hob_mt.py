# -*- coding: utf-8 -*-
"""Unit tests for HOB↔MT section offsets and layout."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.hblr_path import apply_transfer_filter  # noqa: E402
from lib.hob_mt import (  # noqa: E402
    HOB_MT_MTA_BUS_OFFSET,
    HOB_MT_SECTION_TITLES,
    HOB_MT_SIX_EXTRA,
    HOB_MT_SEVEN_EXTRA,
    HOB_MT_WALK_OFFSET,
    SECTION_FERRY_BUS,
    SECTION_NJT_PABT,
    SECTION_SUBWAY,
    _is_pabt_departure_headsign,
    build_hob_mt_sections,
    extract_lincoln_nyc_minutes,
    resolve_lincoln_nyc_minutes,
    six_transfer_offset,
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
    def test_seven_and_six_extras(self):
        base = subway_base_offset()
        self.assertEqual(base, HOB_MT_WALK_OFFSET)
        self.assertEqual(seven_transfer_offset(base), base + HOB_MT_SEVEN_EXTRA)
        self.assertEqual(six_transfer_offset(base), base + HOB_MT_SIX_EXTRA)
        self.assertEqual(seven_transfer_offset(base), 9)
        self.assertEqual(six_transfer_offset(base), 12)

    def test_seven_filter_uses_linctnl_plus_walk_plus_five(self):
        # Plan ``+4+lincoln`` == primary LincTnl (10) + walk 4 (+5 for 7).
        lincoln = _board("LincTnl → NYC", [10], source="panynj-crossingtimes")
        seven = _board("7", [15, 18, 22, 30])
        out = apply_transfer_filter(
            lincoln, seven, seven_transfer_offset(subway_base_offset()), "LincTnl", "7"
        )
        # threshold = 10 + 9 → keep >= 19
        self.assertEqual(_mins(out), [22, 30])
        self.assertEqual(out.get("note"), "LincTnl +9")

    def test_six_filter_uses_linctnl_plus_walk_plus_eight(self):
        lincoln = _board("LincTnl → NYC", [10], source="panynj-crossingtimes")
        six = _board("6", [18, 20, 25, 40])
        out = apply_transfer_filter(
            lincoln, six, six_transfer_offset(subway_base_offset()), "LincTnl", "6"
        )
        # threshold = 10 + 12
        self.assertEqual(_mins(out), [25, 40])
        self.assertEqual(out.get("note"), "LincTnl +12")

    def test_base_filter_note_is_linctnl_plus_four(self):
        lincoln = _board("LincTnl → NYC", [12], source="panynj-crossingtimes")
        subway = _board("42 St-PABT", [10, 14, 16, 20])
        out = apply_transfer_filter(
            lincoln, subway, subway_base_offset(), "LincTnl", "42 St-PABT"
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
            lincoln, subway, subway_base_offset(), "LincTnl", "42 St-PABT"
        )
        self.assertEqual(_mins(out), [])
        self.assertEqual(out.get("empty_hint"), "None catchable · A/E")

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

    def test_build_sections_title_order(self):
        def fetch_json(_url):
            raise RuntimeError("network disabled")

        with mock.patch("lib.hob_mt.get_tunnel_boards", return_value=[]), mock.patch(
            "lib.hob_mt.fetch_njt_willow_board",
            return_value={"label": "32084", "trains": [], "error": None},
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
        self.assertEqual(len(sections[0]["boards"]), 2)
        self.assertEqual(len(sections[-1]["boards"]), 2)
        for section in sections:
            self.assertIn("boards", section)
            self.assertIsInstance(section["boards"], list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
