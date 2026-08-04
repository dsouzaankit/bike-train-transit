# -*- coding: utf-8 -*-
"""Unit tests for Whkn tab boards and filters."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import whkn_bus  # noqa: E402


class WhknFilterTests(unittest.TestCase):
    def test_nyc_headsigns(self):
        self.assertTrue(whkn_bus._is_nyc_bus_headsign("New York via River Road"))
        self.assertTrue(whkn_bus._is_nyc_bus_headsign("NYC"))
        self.assertFalse(whkn_bus._is_nyc_bus_headsign("Fort Lee Med West"))

    def test_fort_lee_headsigns(self):
        self.assertTrue(whkn_bus._is_fort_lee_bound_headsign("Fort Lee Med West"))
        self.assertTrue(
            whkn_bus._is_fort_lee_bound_headsign("Englewood Cliffs via Park Ave")
        )
        self.assertFalse(whkn_bus._is_fort_lee_bound_headsign("New York via River Road"))

    def test_route_filter(self):
        trains = [
            {"line": "158", "destination": "New York via River Road", "minutes": 5},
            {"line": "64", "destination": "Lakewood", "minutes": 6},
            {"line": "156", "destination": "New York", "minutes": 8},
            {"line": "159", "destination": "Fort Lee", "minutes": 9},
        ]
        nyc = whkn_bus._filter_trains(
            trains,
            routes=whkn_bus.WHKN_ROUTES,
            headsign_ok=whkn_bus._is_nyc_bus_headsign,
            max_trains=5,
        )
        self.assertEqual([t["line"] for t in nyc], ["158", "156"])

        fl = whkn_bus._filter_trains(
            trains,
            routes=whkn_bus.WHKN_ROUTES,
            headsign_ok=whkn_bus._is_fort_lee_bound_headsign,
            max_trains=5,
        )
        self.assertEqual([t["line"] for t in fl], ["159"])


class WhknBuildTests(unittest.TestCase):
    @mock.patch("lib.whkn_bus.fetch_pabt_fort_lee_board")
    @mock.patch("lib.whkn_bus.fetch_whkn_nyc_board")
    def test_section_order(self, nyc_mock, pabt_mock):
        nyc_mock.return_value = {"label": "Lincoln Harbor", "trains": []}
        pabt_mock.return_value = {"label": "PABT → Fort Lee", "trains": []}
        sections = whkn_bus.build_whkn_sections()
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["title"], whkn_bus.SECTION_WHKN)
        labels = [b["label"] for b in sections[0]["boards"]]
        self.assertEqual(labels, ["Lincoln Harbor", "PABT → Fort Lee"])

    def test_constants(self):
        self.assertEqual(whkn_bus.WHKN_STOP_ID, "21831")
        self.assertEqual(whkn_bus.WHKN_TRANSIT_STOP_ID, "NJTB:148700")
        self.assertEqual(whkn_bus.WHKN_ROUTES, frozenset({"156", "158", "159"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
