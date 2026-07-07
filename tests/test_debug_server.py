# -*- coding: utf-8 -*-
"""debug_server.py one-tap safe mode entry."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import debug_server  # noqa: E402


class DebugServerTests(unittest.TestCase):
    def test_parse_port_default(self):
        saved = sys.argv
        try:
            sys.argv = ["debug_server.py"]
            self.assertEqual(debug_server._parse_port(), debug_server.DEFAULT_PORT)
        finally:
            sys.argv = saved

    def test_parse_port_flag(self):
        saved = sys.argv
        try:
            sys.argv = ["debug_server.py", "--port", "9000"]
            self.assertEqual(debug_server._parse_port(), 9000)
            sys.argv = ["debug_server.py", "-p", "9001"]
            self.assertEqual(debug_server._parse_port(), 9001)
        finally:
            sys.argv = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
