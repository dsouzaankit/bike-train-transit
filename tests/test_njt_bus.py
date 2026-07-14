# -*- coding: utf-8 -*-
"""Tests for NJTb bus stop filters and Transit board helpers."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import njt_bus  # noqa: E402


class NjtBusFilterTests(unittest.TestCase):
    def test_transit_departure_filter_route_81(self):
        self.assertTrue(
            njt_bus.departure_matches_stop("20747", "81", "Exchange Pl")
        )
        self.assertFalse(
            njt_bus.departure_matches_stop("20747", "81", "Exchange Pl Express")
        )
        self.assertFalse(
            njt_bus.departure_matches_stop("20647", "81", "81 EXPRESS to Exchange")
        )
        self.assertFalse(
            njt_bus.departure_matches_stop("20747", "6", "Journal Square")
        )

    def test_filter_transit_trains_excludes_route_81_express(self):
        raw = [
            {"line": "81", "destination": "Exchange Pl", "minutes": 5, "eta": "5m"},
            {"line": "81", "destination": "Exchange Pl Express", "minutes": 3, "eta": "3m"},
            {"line": "6", "destination": "Journal Square", "minutes": 8, "eta": "8m"},
        ]
        filtered = njt_bus._filter_transit_trains("20747", raw, max_trains=3)
        self.assertEqual([t["destination"] for t in filtered], ["Exchange Pl"])

    def test_transit_departure_filter_route_1(self):
        self.assertTrue(
            njt_bus.departure_matches_stop(
                "30492", "1", "Exchange Pl via River Terminal"
            )
        )
        self.assertTrue(
            njt_bus.departure_matches_stop(
                "20764", "1", "Newark-Ivy Hill via River Term"
            )
        )
        self.assertFalse(
            njt_bus.departure_matches_stop("30492", "12", "Newark")
        )
        self.assertFalse(
            njt_bus.departure_matches_stop("30492", "81", "Exchange Pl")
        )

    def test_filter_transit_trains(self):
        raw = [
            {"line": "81", "destination": "Exchange Pl", "minutes": 5, "eta": "5m"},
            {"line": "6", "destination": "Journal Square", "minutes": 8, "eta": "8m"},
            {"line": "1", "destination": "Newark", "minutes": 9, "eta": "9m"},
        ]
        filtered = njt_bus._filter_transit_trains("20747", raw, max_trains=3)
        self.assertEqual([t["line"] for t in filtered], ["81"])

    def test_stop_button_title_is_address(self):
        self.assertEqual(
            njt_bus.stop_button_title("20747"),
            "Grand St / Arlington Ave",
        )
        self.assertEqual(
            njt_bus.stop_button_title("20647"),
            "Columbus Dr / Grove St",
        )
        for spec in njt_bus.NJT_BUS_STOPS:
            self.assertTrue(spec.get("display_address"))

    def test_sms_url(self):
        self.assertEqual(njt_bus.sms_url("20747"), "sms:69287&body=20747")

    def test_stop_order_east_then_west(self):
        groups = njt_bus.stops_by_direction()
        self.assertEqual([title for title, _ in groups], ["Eastbound", "Westbound"])
        east_ids = [s["stop_id"] for s in groups[0][1]]
        west_ids = [s["stop_id"] for s in groups[1][1]]
        self.assertEqual(east_ids, ["20747", "30492"])
        self.assertEqual(west_ids, ["20764", "20647"])

    def test_transit_stop_ids_present(self):
        for spec in njt_bus.NJT_BUS_STOPS:
            self.assertTrue(spec["transit_stop_id"].startswith("NJTB:"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
