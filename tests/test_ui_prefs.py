# -*- coding: utf-8 -*-
"""Persistent UI prefs (thumb-float handedness)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ui_prefs  # noqa: E402


class UiPrefsTests(unittest.TestCase):
    def test_default_handedness_is_lhd(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ui_prefs.json")
            self.assertEqual(ui_prefs.get_thumb_float_handedness(path=path), "lhd")

    def test_toggle_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ui_prefs.json")
            self.assertEqual(
                ui_prefs.toggle_thumb_float_handedness(path=path), "rhd"
            )
            self.assertEqual(ui_prefs.get_thumb_float_handedness(path=path), "rhd")
            self.assertEqual(
                ui_prefs.toggle_thumb_float_handedness(path=path), "lhd"
            )
            self.assertEqual(ui_prefs.get_thumb_float_handedness(path=path), "lhd")

    def test_normalize_aliases(self):
        self.assertEqual(ui_prefs.normalize_handedness("RHD"), "rhd")
        self.assertEqual(ui_prefs.normalize_handedness("right-handed"), "rhd")
        self.assertEqual(ui_prefs.normalize_handedness("left"), "lhd")
        self.assertEqual(ui_prefs.normalize_handedness(None), "lhd")


if __name__ == "__main__":
    unittest.main(verbosity=2)
