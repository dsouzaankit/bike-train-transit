# -*- coding: utf-8 -*-
"""Thumb-float dual-column pill layout (no overlap, centered stack, LHD/RHD)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bike_train_transit as btt  # noqa: E402


class ThumbFloatLayoutTests(unittest.TestCase):
    def test_lhd_primary_left_of_secondary(self):
        tab_w = 100
        for width in (320, 390, 412, 430):
            primary, secondary = btt.compute_thumb_float_column_centers(
                width, tab_w, handedness="lhd"
            )
            primary_right = primary + tab_w // 2
            secondary_left = secondary - tab_w // 2
            self.assertLessEqual(
                primary_right + btt.THUMB_FLOAT_COLUMN_GAP,
                secondary_left,
                msg="LHD overlap at width %s" % width,
            )
            self.assertLess(primary, secondary)

    def test_rhd_mirrors_lhd(self):
        tab_w = 100
        for width in (320, 390, 412, 430):
            l_primary, l_secondary = btt.compute_thumb_float_column_centers(
                width, tab_w, handedness="lhd"
            )
            r_primary, r_secondary = btt.compute_thumb_float_column_centers(
                width, tab_w, handedness="rhd"
            )
            self.assertLess(l_primary, l_secondary)
            self.assertGreater(r_primary, r_secondary)
            # Ideal gap matches when neither side needs edge clamping.
            if l_primary > tab_w and r_primary < width - tab_w:
                self.assertEqual(l_secondary, r_secondary)
                self.assertEqual(
                    l_secondary - l_primary,
                    r_primary - r_secondary,
                    msg="mirror gap mismatch at width %s" % width,
                )
            primary_left = r_primary - tab_w // 2
            secondary_right = r_secondary + tab_w // 2
            self.assertGreaterEqual(
                primary_left,
                secondary_right + btt.THUMB_FLOAT_COLUMN_GAP,
                msg="RHD overlap at width %s" % width,
            )

    def test_default_handedness_is_lhd(self):
        tab_w = 100
        default = btt.compute_thumb_float_column_centers(390, tab_w)
        lhd = btt.compute_thumb_float_column_centers(390, tab_w, handedness="lhd")
        self.assertEqual(default, lhd)

    def test_shorter_column_bottom_aligns_with_taller(self):
        top, usable_h, btn_h = 47, 763, 50
        gap = btt.THUMB_FLOAT_BTN_GAP
        taller_n, shorter_n = 7, 6
        taller_top = btt.compute_thumb_float_stack_top_y(
            top, usable_h, btn_h, taller_n
        )
        taller_h = taller_n * btn_h + (taller_n - 1) * gap
        shorter_h = shorter_n * btn_h + (shorter_n - 1) * gap
        shorter_top = taller_top + taller_h - shorter_h
        self.assertGreater(shorter_top, taller_top)
        self.assertEqual(shorter_top + shorter_h, taller_top + taller_h)

    def test_stack_centered_not_pinned_to_header(self):
        top, usable_h, btn_h = 47, 763, 50
        gap = btt.THUMB_FLOAT_BTN_GAP
        count = 7
        total_h = count * btn_h + (count - 1) * gap
        stack_top = btt.compute_thumb_float_stack_top_y(top, usable_h, btn_h, count)
        stack_center = stack_top + total_h // 2
        expected_center = top + int(usable_h * btt.THUMB_FLOAT_STACK_Y_RATIO)
        self.assertAlmostEqual(stack_center, expected_center, delta=btn_h)
        self.assertGreater(stack_top, top + 40)

    def test_stack_clears_status_band_under_title(self):
        top, usable_h, btn_h = 47, 763, 50
        header_h = 64 + top
        status_top = header_h + 4
        status_band = status_top + 16 + 10
        stack_top = btt.compute_thumb_float_stack_top_y(
            top,
            usable_h,
            btn_h,
            7,
            min_top_pad=max(8, status_band - top),
        )
        self.assertGreaterEqual(stack_top, status_top + 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
