# -*- coding: utf-8 -*-
"""Persistent HTTP JSON cache."""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http_cache  # noqa: E402


class HttpCacheTests(unittest.TestCase):
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

    def test_normalize_strips_panynj_bust_param(self):
        a = "https://www.panynj.gov/bin/portauthority/ridepath.json?_=111"
        b = "https://www.panynj.gov/bin/portauthority/ridepath.json?_=222"
        self.assertEqual(http_cache.normalize_cache_url(a), http_cache.normalize_cache_url(b))

    def test_subway_query_params_are_part_of_key(self):
        a = "https://subwayinfo.nyc/api/arrivals?station_id=133&direction=N"
        b = "https://subwayinfo.nyc/api/arrivals?station_id=635&direction=N"
        self.assertNotEqual(http_cache.normalize_cache_url(a), http_cache.normalize_cache_url(b))

    def test_memory_and_disk_reuse_within_ttl(self):
        url = "https://example.com/data.json"
        payload = {"ok": True}
        http_cache.store_cached_json(url, payload)
        http_cache.clear_memory()
        self.assertEqual(http_cache.get_cached_json(url), payload)

    def test_expired_disk_entry_returns_none(self):
        url = "https://example.com/old.json"
        key = http_cache._entry_key(url)
        path = http_cache._entry_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "stored_at": time.time() - http_cache.HTTP_CACHE_TTL_SEC - 5,
                    "url": url,
                    "payload": {"stale": True},
                },
                fh,
            )
        self.assertIsNone(http_cache.get_cached_json(url))


if __name__ == "__main__":
    unittest.main(verbosity=2)
