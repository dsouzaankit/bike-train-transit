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

    def test_pabt_keeps_lincoln_harbor_trips_only(self):
        self.assertTrue(
            whkn_bus._serves_lincoln_harbor("158", "Fort Lee")
        )
        self.assertTrue(
            whkn_bus._serves_lincoln_harbor("158", "Fort Lee Med West")
        )
        self.assertTrue(
            whkn_bus._serves_lincoln_harbor("156", "Fort Lee via River Road")
        )
        self.assertTrue(
            whkn_bus._serves_lincoln_harbor("156R", "156r Fort Lee Via River Road")
        )
        self.assertTrue(
            whkn_bus._serves_lincoln_harbor(
                "159", "159r Fort Lee Linwood Park Via River Road"
            )
        )
        self.assertFalse(
            whkn_bus._serves_lincoln_harbor("156", "Englewood Cliffs via Park Ave")
        )
        self.assertFalse(
            whkn_bus._serves_lincoln_harbor("159", "Fort Lee via Blvd East")
        )
        self.assertFalse(
            whkn_bus._serves_lincoln_harbor("159", "Fort Lee")
        )
        self.assertFalse(
            whkn_bus._serves_lincoln_harbor("158", "New York via River Road")
        )

    def test_route_filter(self):
        trains = [
            {"line": "158", "destination": "New York via River Road", "minutes": 5},
            {"line": "64", "destination": "Lakewood", "minutes": 6},
            {"line": "156", "destination": "New York", "minutes": 8},
            {"line": "159", "destination": "Fort Lee via River Road", "minutes": 9},
            {"line": "156", "destination": "Englewood Cliffs via Park Ave", "minutes": 11},
            {"line": "158", "destination": "Fort Lee", "minutes": 12},
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
            trip_ok=lambda train: whkn_bus._serves_lincoln_harbor(
                train.get("line"), train.get("destination")
            ),
        )
        self.assertEqual(
            [(t["line"], t["destination"]) for t in fl],
            [
                ("159", "Fort Lee via River Road"),
                ("158", "Fort Lee"),
            ],
        )

    def test_bare_159_linwood_park_skips_lincoln_harbor(self):
        """159 without 'via River Road' is the Blvd East / Palisades variant."""
        self.assertFalse(
            whkn_bus._serves_lincoln_harbor("159", "Fort Lee Linwood Park")
        )


class WhknFetchTests(unittest.TestCase):
    def test_pabt_parse_uses_fort_lee_headsign_filter(self):
        """Busy PABT feed must filter during parse or Whkn ETAs get truncated away."""
        payload = {"route_departures": []}
        parse_calls = []
        fetch_kwargs = []

        def fake_parse(payload_arg, dest_ok, *, max_trains=12, now_epoch=None):
            parse_calls.append((dest_ok, max_trains))
            # Unrelated PABT buses would starve a True/accept-all pool.
            raw = [
                {"line": "355", "destination": "American Dream", "minutes": 5},
                {"line": "319", "destination": "Atlantic City", "minutes": 5},
                {"line": "158", "destination": "Fort Lee Med West", "minutes": 6},
            ]
            return [
                row
                for row in raw
                if dest_ok(row["destination"])
            ][:max_trains]

        def fake_fetch(stop_id, *, max_departures=10):
            fetch_kwargs.append({"stop_id": stop_id, "max_departures": max_departures})
            return payload

        with mock.patch("lib.transit_app.has_api_key", return_value=True), mock.patch(
            "lib.transit_app.fetch_stop_departures", side_effect=fake_fetch
        ), mock.patch(
            "lib.transit_app.parse_route_departures", side_effect=fake_parse
        ), mock.patch(
            "lib.pabt_gates.annotate_pabt_board_with_gates", side_effect=lambda b: b
        ):
            board = whkn_bus.fetch_pabt_fort_lee_board()

        self.assertEqual(len(parse_calls), 1)
        dest_ok, max_trains = parse_calls[0]
        self.assertTrue(dest_ok("Fort Lee Med West"))
        self.assertFalse(dest_ok("American Dream"))
        self.assertGreaterEqual(max_trains, 40)
        self.assertEqual(fetch_kwargs[0]["stop_id"], whkn_bus.PABT_TRANSIT_STOP_ID)
        self.assertGreaterEqual(fetch_kwargs[0]["max_departures"], 40)
        self.assertEqual(
            [(t["line"], t["destination"]) for t in board["trains"]],
            [("158", "Fort Lee Med West")],
        )


class WhknBuildTests(unittest.TestCase):
    @mock.patch("lib.whkn_bus.fetch_lincoln_harbor_hblr_board")
    @mock.patch("lib.whkn_bus.fetch_pabt_fort_lee_board")
    @mock.patch("lib.whkn_bus.fetch_whkn_nyc_board")
    def test_section_order(self, nyc_mock, pabt_mock, hblr_mock):
        nyc_mock.return_value = {"label": "Lincoln Harbor", "trains": []}
        pabt_mock.return_value = {"label": "PABT → River Rd", "trains": []}
        hblr_mock.return_value = {"label": "HBLR", "trains": []}
        sections = whkn_bus.build_whkn_sections()
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["title"], whkn_bus.SECTION_WHKN)
        labels = [b["label"] for b in sections[0]["boards"]]
        self.assertEqual(labels, ["Lincoln Harbor", "PABT → River Rd", "HBLR"])

    def test_constants(self):
        self.assertEqual(whkn_bus.WHKN_STOP_ID, "21831")
        self.assertEqual(whkn_bus.WHKN_TRANSIT_STOP_ID, "NJTB:148700")
        self.assertEqual(whkn_bus.WHKN_ROUTES, frozenset({"156", "158", "159"}))
        self.assertEqual(whkn_bus.PABT_RIVER_RD_DISPLAY, "PABT → River Rd")
        self.assertEqual(whkn_bus.WHKN_HBLR_STATION, "Lincoln Harbor")
        self.assertEqual(whkn_bus.WHKN_HBLR_DIRECTION, "lincoln_harbor_south")

    def test_hblr_keeps_west_side_and_hoboken(self):
        with mock.patch(
            "lib.light_rail.get_hblr_board",
            return_value={
                "label": "HBLR",
                "trains": [
                    {"destination": "Hoboken", "minutes": 3, "eta": "3m"},
                    {"destination": "West Side Av", "minutes": 8, "eta": "8m"},
                ],
                "_raw_trains": [
                    {"destination": "Hoboken", "minutes": 3, "eta": "3m"},
                    {"destination": "West Side Av", "minutes": 8, "eta": "8m"},
                    {"destination": "Tonnelle Av", "minutes": 4, "eta": "4m"},
                ],
                "error": None,
                "source": "transit",
            },
        ):
            board = whkn_bus.fetch_lincoln_harbor_hblr_board()
        dests = [t["destination"] for t in board["trains"]]
        self.assertEqual(dests, ["Hoboken", "West Side Av"])
        self.assertEqual(board["label"], "HBLR")


class LincolnHarborHblrFilterTests(unittest.TestCase):
    def test_southbound_destinations(self):
        from lib.light_rail import _is_lincoln_harbor_southbound

        self.assertTrue(_is_lincoln_harbor_southbound("West Side Avenue Hudson-Bergen"))
        self.assertTrue(_is_lincoln_harbor_southbound("Hoboken Terminal Hudson-Bergen"))
        self.assertFalse(_is_lincoln_harbor_southbound("Tonnelle Avenue Hudson-Bergen"))
        self.assertFalse(_is_lincoln_harbor_southbound("8th Street"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
