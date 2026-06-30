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

    def test_stats_track_hits_and_stores(self):
        url = "https://example.com/stats.json"
        http_cache.reset_stats()
        http_cache.store_cached_json(url, {"a": 1})
        http_cache.get_cached_json(url)
        stats = http_cache.stats_snapshot()
        self.assertEqual(stats["stores"], 1)
        self.assertGreaterEqual(stats["hits"], 1)

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

    def test_corrupt_memory_timestamp_falls_back_to_disk(self):
        url = "https://example.com/corrupt-mem.json"
        key = http_cache._entry_key(url)
        payload = {"ok": True}
        http_cache._memory[key] = ("not-a-timestamp", payload)
        path = http_cache._entry_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        stored_at = time.time()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {"stored_at": stored_at, "url": url, "payload": payload},
                fh,
            )
        self.assertEqual(http_cache.get_cached_json(url), payload)

    def test_string_stored_at_on_disk_is_coerced(self):
        url = "https://example.com/string-ts.json"
        key = http_cache._entry_key(url)
        path = http_cache._entry_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        stored_at = time.time()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "stored_at": str(stored_at),
                    "url": url,
                    "payload": {"numeric_string_ts": True},
                },
                fh,
            )
        self.assertEqual(
            http_cache.get_cached_json(url), {"numeric_string_ts": True}
        )

    def test_min_remaining_ttl_reports_soonest_entry(self):
        url_old = "https://example.com/oldish.json"
        url_new = "https://example.com/fresh.json"
        now = time.time()
        http_cache._memory[http_cache._entry_key(url_old)] = (
            now - 90,
            {"a": 1},
        )
        http_cache._memory[http_cache._entry_key(url_new)] = (
            now - 10,
            {"b": 2},
        )
        remaining = http_cache.min_remaining_ttl_sec(now=now)
        self.assertIsNotNone(remaining)
        assert remaining is not None
        self.assertGreaterEqual(remaining, 29)
        self.assertLessEqual(remaining, 31)

    def test_min_remaining_ttl_none_when_empty(self):
        self.assertIsNone(http_cache.min_remaining_ttl_sec())


if __name__ == "__main__":
    unittest.main(verbosity=2)
