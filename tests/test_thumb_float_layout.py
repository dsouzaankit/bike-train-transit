# -*- coding: utf-8 -*-
"""Thumb-float dual-column pill layout (no overlap, centered stack)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bike_train_transit as btt  # noqa: E402


class ThumbFloatLayoutTests(unittest.TestCase):
    def test_columns_do_not_overlap_on_phone_widths(self):
        tab_w = 100
        for width in (320, 390, 412, 430):
            cbike_center, transit_center = btt.compute_thumb_float_column_centers(
                width, tab_w
            )
            cbike_right = cbike_center + tab_w // 2
            transit_left = transit_center - tab_w // 2
            self.assertLessEqual(
                cbike_right + btt.THUMB_FLOAT_COLUMN_GAP,
                transit_left,
                msg="overlap at width %s" % width,
            )

    def test_top_rows_align_cbike_jc_and_from_jc(self):
        top, usable_h, btn_h = 47, 763, 50
        gap = btt.THUMB_FLOAT_BTN_GAP
        stack_top = btt.compute_thumb_float_stack_top_y(top, usable_h, btn_h, 5)
        # Both columns grow from the same stack_top (Cbike JC beside From JC).
        row2_y = stack_top + btn_h + gap
        self.assertEqual(row2_y, 389 + btn_h + gap)

    def test_stack_centered_not_pinned_to_header(self):
        top, usable_h, btn_h = 47, 763, 50
        gap = btt.THUMB_FLOAT_BTN_GAP
        count = 5
        total_h = count * btn_h + (count - 1) * gap
        stack_top = btt.compute_thumb_float_stack_top_y(top, usable_h, btn_h, count)
        stack_center = stack_top + total_h // 2
        expected_center = top + int(usable_h * btt.THUMB_FLOAT_STACK_Y_RATIO)
        self.assertAlmostEqual(stack_center, expected_center, delta=btn_h)
        self.assertGreater(stack_top, top + 70)


if __name__ == "__main__":
    unittest.main(verbosity=2)
