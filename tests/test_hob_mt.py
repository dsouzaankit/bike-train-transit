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
    SECTION_MTA_BUS,
    SECTION_NJT_BUS,
    SECTION_NYWATERWAY,
    SECTION_PABT,
    SECTION_SUBWAY,
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
        self.assertEqual(subway_base_offset(10), HOB_MT_WALK_OFFSET + 10)
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
        base = subway_base_offset(10)
        self.assertEqual(base, 14)
        self.assertEqual(seven_transfer_offset(base), base + HOB_MT_SEVEN_EXTRA)
        self.assertEqual(six_transfer_offset(base), base + HOB_MT_SIX_EXTRA)
        self.assertEqual(seven_transfer_offset(base), 19)
        self.assertEqual(six_transfer_offset(base), 22)

    def test_seven_filter_uses_base_plus_five(self):
        base = subway_base_offset(10)
        now = _board("now", [0], source="synthetic")
        seven = _board("7", [15, 18, 22, 30])
        out = apply_transfer_filter(
            now, seven, seven_transfer_offset(base), "Lincoln", "7"
        )
        # threshold = 0 + 19 → keep >= 19
        self.assertEqual(_mins(out), [22, 30])
        self.assertIn("+%s" % (base + HOB_MT_SEVEN_EXTRA), out.get("note") or "")

    def test_six_filter_uses_base_plus_eight(self):
        base = subway_base_offset(10)
        now = _board("now", [0], source="synthetic")
        six = _board("6", [18, 20, 25, 40])
        out = apply_transfer_filter(
            now, six, six_transfer_offset(base), "Lincoln", "6"
        )
        # threshold = 0 + 22
        self.assertEqual(_mins(out), [25, 40])

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
                SECTION_NJT_BUS,
                SECTION_PABT,
                SECTION_SUBWAY,
                SECTION_NYWATERWAY,
                SECTION_MTA_BUS,
            ],
        )

    def test_build_sections_title_order(self):
        def fetch_json(_url):
            raise RuntimeError("network disabled")

        with mock.patch("lib.hob_mt.get_tunnel_boards", return_value=[]), mock.patch(
            "lib.hob_mt.fetch_njt_willow_board",
            return_value={"label": "32084", "trains": [], "error": None},
        ), mock.patch(
            "lib.hob_mt.fetch_pabt_board",
            return_value={"label": "PABT", "trains": [], "error": None, "note": "gate data TBD"},
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
        for section in sections:
            self.assertIn("boards", section)
            self.assertIsInstance(section["boards"], list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
