# -*- coding: utf-8 -*-
"""Cross-check PDF offline HBLR schedule against saved Transit API snapshots.

Fixtures: tests/fixtures/transit_hblr/*.json (refresh with tools/capture_transit_hblr_fixtures.py).
When these tests fail, rebuild or tune lib/hblr_schedule.py so PDF fallback tracks live service.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hblr_transit_reference import (  # noqa: E402
    FIXTURE_DIR,
    MANIFEST_PATH,
    extract_reference_departures,
    is_in_pdf_explicit,
    list_fixture_ids,
    load_fixture,
    match_pdf_board,
    match_pdf_explicit_times,
    pdf_board_at,
    pdf_explicit_minutes,
)


class HblrTransitPdfSyncTests(unittest.TestCase):
    """Each live Transit HBLR API board vs PDF parser at the same captured_at."""

    def test_fixture_bundle_present(self):
        self.assertTrue(os.path.isdir(FIXTURE_DIR), msg="run tools/capture_transit_hblr_fixtures.py")
        self.assertTrue(os.path.isfile(MANIFEST_PATH))
        ids = list_fixture_ids()
        self.assertEqual(
            set(ids),
            {"lsp_northbound", "exchange_southbound", "newport_southbound"},
        )

    def test_transit_snapshots_align_with_pdf_schedule(self):
        for fixture_id in list_fixture_ids():
            with self.subTest(fixture=fixture_id):
                fixture = load_fixture(fixture_id)
                when, reference = extract_reference_departures(fixture)
                self.assertGreater(
                    len(reference),
                    0,
                    msg="no catchable Transit departures in snapshot",
                )
                station = fixture["station"]
                direction = fixture["direction"]

                explicit = pdf_explicit_minutes(station, direction, when)
                self.assertGreater(len(explicit), 0, msg="empty PDF pool")

                time_errors = match_pdf_explicit_times(reference, explicit, when)
                self.assertEqual(time_errors, [], msg="; ".join(time_errors))

                explicit_ref = [
                    train
                    for train in reference
                    if is_in_pdf_explicit(train["clock_minute"], explicit)
                ]
                if not explicit_ref:
                    # Midday weekday captures only hit the PDF gap — still validates API fixture shape.
                    continue

                pdf_pairs = pdf_board_at(station, direction, when)
                board_errors = match_pdf_board(explicit_ref, pdf_pairs)
                self.assertEqual(board_errors, [], msg="; ".join(board_errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
