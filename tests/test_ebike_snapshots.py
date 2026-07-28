# -*- coding: utf-8 -*-
"""E-bike counts on Citibike station cards (per-tab snapshot builder)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bike_train_transit as btt  # noqa: E402


class EbikeSnapshotTests(unittest.TestCase):
    def test_get_snapshots_includes_ebikes_for_all_stations(self):
        names = list(btt.STATIONS)
        lookup_by_id = {str(i + 1): name for i, name in enumerate(names)}
        lookup_by_name = {name.casefold(): str(i + 1) for i, name in enumerate(names)}

        def fake_status():
            stations = []
            for index, name in enumerate(names):
                stations.append(
                    {
                        "station_id": str(index + 1),
                        "num_bikes_available": 4,
                        "num_ebikes_available": index + 1,
                        "num_docks_available": 10,
                        "is_renting": 1,
                        "is_returning": 1,
                    }
                )
            return {"data": {"stations": stations}}

        with patch.object(btt, "station_lookup", return_value=(lookup_by_id, lookup_by_name)):
            with patch.object(btt, "fetch_json", return_value=fake_status()):
                snapshots = btt.get_snapshots()

        self.assertEqual(len(snapshots), len(names))
        for index, snapshot in enumerate(snapshots):
            self.assertEqual(snapshot["ebikes"], index + 1)

    def test_get_snapshots_for_tab_only_returns_that_tabs_stations(self):
        cfg = btt.CBIKE_TAB_CONFIG["cbike_hob"]
        names = list(cfg["stations"])
        lookup_by_id = {str(i + 1): name for i, name in enumerate(names)}
        lookup_by_name = {name.casefold(): str(i + 1) for i, name in enumerate(names)}

        def fake_status():
            return {
                "data": {
                    "stations": [
                        {
                            "station_id": str(i + 1),
                            "num_bikes_available": 2,
                            "num_ebikes_available": 1,
                            "num_docks_available": 8,
                            "is_renting": 1,
                            "is_returning": 1,
                        }
                        for i in range(len(names))
                    ]
                }
            }

        with patch.object(btt, "station_lookup", return_value=(lookup_by_id, lookup_by_name)):
            with patch.object(btt, "fetch_json", return_value=fake_status()):
                snapshots = btt.get_snapshots_for_tab("cbike_hob")

        self.assertEqual(len(snapshots), 6)
        self.assertEqual(snapshots[0]["region"], "HOB")


if __name__ == "__main__":
    unittest.main(verbosity=2)
