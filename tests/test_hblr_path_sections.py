# -*- coding: utf-8 -*-
"""HBLR ↔ PATH section layout tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.hblr_path import build_hblr_path_sections  # noqa: E402


class HblrPathSectionLayoutTests(unittest.TestCase):
    def test_lsp_primary_shared_once(self):
        sections = build_hblr_path_sections({})
        outbound = sections[0]
        self.assertEqual(outbound["layout"], "shared_primary")
        self.assertEqual(outbound["primary"]["label"], "Liberty State Park")
        self.assertEqual(len(outbound["connections"]), 2)
        labels = [conn["board"]["label"] for conn in outbound["connections"]]
        self.assertEqual(labels, ["Exchange Place", "Newport PATH"])

    def test_inbound_sections_unchanged(self):
        sections = build_hblr_path_sections({})
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[1]["title"], "PATH WTC → HBLR")
        self.assertEqual(sections[2]["title"], "PATH 33rd St → HBLR")


if __name__ == "__main__":
    unittest.main(verbosity=2)
