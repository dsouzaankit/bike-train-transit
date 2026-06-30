# -*- coding: utf-8 -*-
"""GBFS cache validation and corrupt-entry recovery."""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bike_train_transit as btt  # noqa: E402
from lib import http_cache  # noqa: E402

GBFS_INFO = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"


def _status_shaped_payload():
    return {
        "data": {
            "stations": [
                {
                    "station_id": "72",
                    "num_bikes_available": 3,
                    "num_docks_available": 16,
                }
            ]
        }
    }


def _info_shaped_payload():
    return {
        "data": {
            "stations": [
                {"station_id": "72", "name": "W 52 St & 9 Ave"},
            ]
        }
    }


class GbfsCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        http_cache.set_cache_dir_for_tests(self._tmpdir)
        http_cache.clear_all()
        self._saved_no_cache = os.environ.pop("BIKE_TRAIN_TRANSIT_NO_HTTP_CACHE", None)

    def tearDown(self):
        http_cache.set_cache_dir_for_tests(None)
        http_cache.clear_all()
        if self._saved_no_cache is not None:
            os.environ["BIKE_TRAIN_TRANSIT_NO_HTTP_CACHE"] = self._saved_no_cache

    def test_status_payload_rejected_for_station_information_url(self):
        with self.assertRaises(ValueError) as ctx:
            btt._validate_gbfs_payload(GBFS_INFO, _status_shaped_payload())
        self.assertIn("missing name", str(ctx.exception))

    def test_fetch_json_rejects_corrupt_cache_and_refetches(self):
        http_cache.store_cached_json(GBFS_INFO, _status_shaped_payload())
        calls = {"n": 0}

        class _Resp:
            def read(self):
                return json.dumps(_info_shaped_payload()).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            return _Resp()

        old = btt.urllib.request.urlopen
        btt.urllib.request.urlopen = fake_urlopen
        try:
            payload = btt.fetch_json(GBFS_INFO)
        finally:
            btt.urllib.request.urlopen = old

        self.assertEqual(calls["n"], 1)
        self.assertEqual(payload["data"]["stations"][0]["name"], "W 52 St & 9 Ave")

    def test_invalidate_drops_disk_entry(self):
        http_cache.store_cached_json(GBFS_INFO, _info_shaped_payload())
        http_cache.clear_memory()
        self.assertIsNotNone(http_cache.get_cached_json(GBFS_INFO))
        http_cache.invalidate_cached_json(GBFS_INFO)
        http_cache.clear_memory()
        self.assertIsNone(http_cache.get_cached_json(GBFS_INFO))


if __name__ == "__main__":
    unittest.main(verbosity=2)
