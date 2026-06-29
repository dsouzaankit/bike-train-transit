# -*- coding: utf-8 -*-
"""PATH destination shortening for compact HBLR-tab cards."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.path_trains import _short_destination  # noqa: E402


class PathDestinationShortTests(unittest.TestCase):
    def test_wtc_variants(self):
        self.assertEqual(_short_destination("World Trade Center"), "WTC")
        self.assertEqual(_short_destination("To World Trade Center"), "WTC")

    def test_33rd_variants(self):
        self.assertEqual(_short_destination("33rd Street"), "33rd St")
        self.assertEqual(_short_destination("33rd Street via Hoboken"), "33rd via Hob")
        self.assertEqual(_short_destination("Journal Square via Hoboken"), "JSQ via Hob")

    def test_journal_square_33rd_combo(self):
        self.assertEqual(_short_destination("Journal Square-33rd Street"), "33rd St")


if __name__ == "__main__":
    unittest.main(verbosity=2)
