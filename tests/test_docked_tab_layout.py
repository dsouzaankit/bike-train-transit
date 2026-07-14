# -*- coding: utf-8 -*-
"""Docked header tab ribbon wraps at four pills per row."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bike_train_transit as btt  # noqa: E402


class DockedTabLayoutTests(unittest.TestCase):
    def test_eight_tabs_use_two_rows_of_four(self):
        bar_h, tab_w, frames = btt.compute_docked_tab_layout(390, 8)
        self.assertEqual(len(frames), 8)
        self.assertEqual(frames[0][1], 0)
        self.assertEqual(frames[3][1], 0)
        self.assertGreater(frames[4][1], 0)
        self.assertEqual(frames[4][1], frames[7][1])
        row0_ys = {frame[1] for frame in frames[:4]}
        row1_ys = {frame[1] for frame in frames[4:]}
        self.assertEqual(len(row0_ys), 1)
        self.assertEqual(len(row1_ys), 1)
        self.assertGreater(bar_h, btt.TAB_BAR_ROW_HEIGHT)

    def test_four_tabs_stay_on_one_row(self):
        bar_h, _tab_w, frames = btt.compute_docked_tab_layout(390, 4)
        self.assertEqual(len({frame[1] for frame in frames}), 1)
        self.assertEqual(bar_h, btt.TAB_BAR_ROW_HEIGHT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
