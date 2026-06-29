# -*- coding: utf-8 -*-
"""Unit tests for Transit App HBLR departure parsing."""

from __future__ import annotations

import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import transit_app  # noqa: E402
from lib.light_rail import (  # noqa: E402
    _fetch_transit_departures,
    _is_northbound_destination,
    _is_towards_liberty_state_park,
)

EXCHANGE_SAMPLE = {
    "route_departures": [
        {
            "global_route_id": "NJTR:156744",
            "merged_itineraries": [
                {
                    "direction_id": 0,
                    "itineraries": [
                        {
                            "headsign": "Hoboken Terminal",
                            "internal_itinerary_id": "46",
                        }
                    ],
                    "schedule_items": [
                        {
                            "departure_time": 2000000000,
                            "internal_itinerary_id": "46",
                            "is_cancelled": False,
                            "is_real_time": True,
                        },
                        {
                            "departure_time": 2000001200,
                            "internal_itinerary_id": "46",
                            "is_cancelled": False,
                            "is_real_time": False,
                        },
                    ],
                },
                {
                    "direction_id": 1,
                    "itineraries": [
                        {
                            "headsign": "8th Street",
                            "internal_itinerary_id": "12",
                        }
                    ],
                    "schedule_items": [
                        {
                            "departure_time": 2000000600,
                            "internal_itinerary_id": "12",
                            "is_cancelled": False,
                            "is_real_time": False,
                        }
                    ],
                },
            ],
        },
        {
            "global_route_id": "NJTR:156743",
            "merged_itineraries": [
                {
                    "direction_id": 0,
                    "itineraries": [
                        {
                            "headsign": "Tonnelle Avenue",
                            "internal_itinerary_id": "61",
                        }
                    ],
                    "schedule_items": [
                        {
                            "departure_time": 2000001800,
                            "internal_itinerary_id": "61",
                            "is_cancelled": False,
                            "is_real_time": False,
                        }
                    ],
                },
                {
                    "direction_id": 1,
                    "itineraries": [{"headsign": "West Side Avenue", "internal_itinerary_id": "9"}],
                    "schedule_items": [
                        {
                            "departure_time": 2000002400,
                            "internal_itinerary_id": "9",
                            "is_cancelled": False,
                            "is_real_time": False,
                        }
                    ],
                },
            ],
        },
    ]
}


class TransitAppParseTests(unittest.TestCase):
    def setUp(self):
        transit_app.clear_departure_cache()

    def test_northbound_filters_hoboken_and_tonnelle(self):
        now = 2000000000 - 120
        trains = transit_app.parse_route_departures(
            EXCHANGE_SAMPLE,
            _is_northbound_destination,
            now_epoch=now,
            max_trains=10,
        )
        dests = {t["destination"] for t in trains}
        self.assertIn("Hoboken Terminal", dests)
        self.assertIn("Tonnelle Avenue", dests)
        self.assertNotIn("8th Street", dests)
        self.assertNotIn("22nd Street Light Rail Station", dests)

    def test_northbound_rejects_22nd_street(self):
        self.assertFalse(_is_northbound_destination("22nd Street Light Rail Station"))
        self.assertTrue(_is_towards_liberty_state_park("22nd Street Light Rail Station"))

    def test_route_display_line_skips_vehicle_icon(self):
        from lib.transit_app import _route_display_line

        line = _route_display_line(
            {
                "route_short_name": None,
                "compact_display_short_name": {
                    "elements": ["vehicle-rail-njtlr", "", None],
                },
            }
        )
        self.assertIsNone(line)
        self.assertEqual(
            _route_display_line({"route_short_name": "Hudson-Bergen"}),
            "Hudson-Bergen",
        )

    def test_southbound_filters_bayonne_branches(self):
        now = 2000000000 - 120
        trains = transit_app.parse_route_departures(
            EXCHANGE_SAMPLE,
            _is_towards_liberty_state_park,
            now_epoch=now,
            max_trains=10,
        )
        dests = {t["destination"] for t in trains}
        self.assertIn("8th Street", dests)
        self.assertIn("West Side Avenue", dests)
        self.assertNotIn("Hoboken Terminal", dests)

    def test_minutes_until_departure(self):
        now = 2000000000 - 90
        trains = transit_app.parse_route_departures(
            EXCHANGE_SAMPLE,
            _is_northbound_destination,
            now_epoch=now,
            max_trains=1,
        )
        self.assertEqual(trains[0]["minutes"], 2)

    @mock.patch("lib.transit_app.fetch_stop_departures")
    def test_light_rail_prefers_transit(self, fetch_mock):
        fetch_mock.return_value = EXCHANGE_SAMPLE
        station = {
            "label": "Exchange Place",
            "transit_stop_id": "NJTR:3076",
        }
        with mock.patch("lib.transit_app.has_api_key", return_value=True):
            trains = _fetch_transit_departures(station, "northbound", 6)
        self.assertTrue(trains)
        self.assertEqual(trains[0]["destination"], "Hoboken")
        self.assertNotIn("line", trains[0])
        fetch_mock.assert_called_once()


class TransitAppCacheTests(unittest.TestCase):
    def setUp(self):
        transit_app.clear_departure_cache()

    @mock.patch("lib.transit_app._get_json")
    def test_stop_departures_cached(self, get_mock):
        get_mock.return_value = {"route_departures": []}
        with mock.patch("lib.transit_app._load_api_key", return_value="test-key"):
            transit_app.fetch_stop_departures("NJTR:3076")
            transit_app.fetch_stop_departures("NJTR:3076")
        self.assertEqual(get_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
