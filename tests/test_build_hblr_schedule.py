# -*- coding: utf-8 -*-
"""Unit tests for HBLR PDF time-token parsing."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.build_hblr_schedule import minutes_to_pdf_token, parse_time_sequence  # noqa: E402


class ParseTimeSequenceTests(unittest.TestCase):
    def test_morning_through_afternoon_noon_reset(self):
        # Weekend LSP north AM band excerpt: 11:55 AM → noon → 1:01 PM.
        tokens = ["1155", "1201", "1255", "101", "235"]
        times = parse_time_sequence(tokens, pm_band=False)
        self.assertEqual(times, [11 * 60 + 55, 12 * 60 + 1, 12 * 60 + 55, 13 * 60 + 1, 14 * 60 + 35])

    def test_pm_band_evening_through_late_night_reset(self):
        # Weekend LSP north PM band tail: 11:55 PM → midnight → 1:36 AM.
        tokens = ["1155", "1201", "1225", "1255", "106", "136"]
        times = parse_time_sequence(tokens, pm_band=True)
        self.assertEqual(times, [1, 25, 55, 66, 96, 23 * 60 + 55])

    def test_late_night_includes_245_am(self):
        tokens = ["1155", "1201", "245", "246"]
        times = parse_time_sequence(tokens, pm_band=True)
        self.assertIn(2 * 60 + 45, times)
        self.assertNotIn(2 * 60 + 46, times)

    def test_pm_band_starts_in_afternoon(self):
        tokens = ["421", "855", "901"]
        times = parse_time_sequence(tokens, pm_band=True)
        self.assertEqual(times, [16 * 60 + 21, 20 * 60 + 55, 21 * 60 + 1])


class MinutesToPdfTokenTests(unittest.TestCase):
    def test_exchange_weekend_service_window_tokens(self):
        self.assertEqual(minutes_to_pdf_token(328), "528")
        self.assertEqual(minutes_to_pdf_token(104), "144")
        self.assertEqual(minutes_to_pdf_token(23 * 60 + 49), "1149")

    def test_midnight_and_pm(self):
        self.assertEqual(minutes_to_pdf_token(4), "1204")
        self.assertEqual(minutes_to_pdf_token(16 * 60 + 29), "429")


if __name__ == "__main__":
    unittest.main(verbosity=2)
