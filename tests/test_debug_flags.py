# -*- coding: utf-8 -*-
"""Debug inactive-source flags."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.debug_flags import inactive_sources, inactive_summary, is_active, set_inactive  # noqa: E402


class DebugFlagsTests(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("BIKE_TRAIN_TRANSIT_INACTIVE")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("BIKE_TRAIN_TRANSIT_INACTIVE", None)
        else:
            os.environ["BIKE_TRAIN_TRANSIT_INACTIVE"] = self._saved

    def test_empty_env_all_active(self):
        os.environ.pop("BIKE_TRAIN_TRANSIT_INACTIVE", None)
        self.assertEqual(inactive_sources(), frozenset())
        self.assertTrue(is_active("citibike"))
        self.assertEqual(inactive_summary(), "")

    def test_inactive_from_env(self):
        os.environ["BIKE_TRAIN_TRANSIT_INACTIVE"] = "subway, path"
        self.assertEqual(inactive_sources(), frozenset({"subway", "path"}))
        self.assertFalse(is_active("subway"))
        self.assertTrue(is_active("hblr"))
        self.assertEqual(inactive_summary(), "path, subway")

    def test_set_inactive(self):
        set_inactive("hblr", "citibike")
        self.assertEqual(inactive_summary(), "citibike, hblr")


if __name__ == "__main__":
    unittest.main(verbosity=2)
