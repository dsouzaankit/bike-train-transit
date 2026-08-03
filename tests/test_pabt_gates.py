# -*- coding: utf-8 -*-
"""Unit tests for PABT gate schedule parse / resolve / annotate."""

import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import pabt_gates  # noqa: E402


SAMPLE_119 = """
<html><body>
<div>6:00 AM - 10:00 PM</div>
<div>Gate 210</div>
<div>Door 1</div>
<div>10:01 PM - 1:00 AM</div>
<div>Gate 322</div>
<div>1:01 AM - 5:59 AM</div>
<div>Gate 80</div>
</body></html>
"""

SAMPLE_126 = """
<html><body>
<div>Except &quot;L&quot; trips</div>
<div>6:00 AM - 10:00 PM</div>
<div>Gate 213</div>
<div>&quot;L&quot; trips ONLY</div>
<div>6:00 AM - 10:00 PM</div>
<div>Gate 214</div>
<div>All trips</div>
<div>10:01 PM - 1:00 AM</div>
<div>Gate 323</div>
<div>All trips</div>
<div>1:01 AM - 5:59 AM</div>
<div>Gate 79</div>
</body></html>
"""


class PabtGatesTests(unittest.TestCase):
    def test_parse_119_windows(self):
        windows = pabt_gates.parse_route_html(SAMPLE_119, "119")
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0]["gate"], "210")
        self.assertEqual(windows[0]["door"], "1")
        self.assertEqual(windows[1]["gate"], "322")
        self.assertEqual(windows[2]["gate"], "80")

    def test_parse_126_notes(self):
        windows = pabt_gates.parse_route_html(SAMPLE_126, "126")
        self.assertEqual(
            [(w["gate"], w["note"]) for w in windows],
            [
                ("213", "except_l"),
                ("214", "l_only"),
                ("323", "all"),
                ("79", "all"),
            ],
        )

    def test_overnight_window(self):
        self.assertTrue(pabt_gates.window_contains(1321, 60, 23 * 60))  # 11 PM
        self.assertTrue(pabt_gates.window_contains(1321, 60, 30))  # 12:30 AM
        self.assertFalse(pabt_gates.window_contains(1321, 60, 12 * 60))

    def test_active_at_4am_uses_overnight_gate(self):
        now = datetime.datetime(2026, 8, 3, 4, 12)
        data = pabt_gates.builtin_schedule_payload()
        active = pabt_gates.active_windows("119", now=now, data=data)
        self.assertEqual([w["gate"] for w in active], ["80"])
        active126 = pabt_gates.active_windows("126", now=now, data=data)
        self.assertEqual([w["gate"] for w in active126], ["79"])

    def test_resolve_126_l_vs_regular(self):
        now = datetime.datetime(2026, 8, 3, 12, 0)
        data = pabt_gates.builtin_schedule_payload()
        reg = pabt_gates.resolve_gate_for_departure(
            "126", "Hoboken", now=now, data=data
        )
        lim = pabt_gates.resolve_gate_for_departure(
            "126", "Hoboken L", now=now, data=data
        )
        self.assertEqual(reg["gate"], "213")
        self.assertEqual(lim["gate"], "214")

    def test_annotate_pabt_board(self):
        now = datetime.datetime(2026, 8, 3, 12, 0)
        data = pabt_gates.builtin_schedule_payload()
        board = {
            "label": "PABT dep",
            "trains": [
                {
                    "line": "119",
                    "minutes": 5,
                    "eta": "5m",
                    "destination": "Bayonne",
                },
                {
                    "line": "126",
                    "minutes": 8,
                    "eta": "8m",
                    "destination": "Hoboken L",
                },
            ],
            "by_line": True,
        }
        out = pabt_gates.annotate_pabt_board_with_gates(board, now=now, data=data)
        self.assertIn("Gate 210", out["trains"][0]["destination"])
        self.assertIn("Gate 214", out["trains"][1]["destination"])

    def test_scrape_refresh_persists(self):
        html_by_url = {
            "https://portauthoritygate.com/119": SAMPLE_119,
            "https://portauthoritygate.com/123": SAMPLE_119.replace("210", "211").replace(
                "322", "303"
            ).replace("80", "79"),
            "https://portauthoritygate.com/126": SAMPLE_126,
        }

        def fetch(url):
            return html_by_url[url]

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pabt_gates_data.json")
            payload = pabt_gates.refresh_schedules_from_web(
                fetch_html=fetch, path=path
            )
            self.assertEqual(payload["routes"]["119"][0]["gate"], "210")
            self.assertEqual(payload["routes"]["126"][1]["gate"], "214")
            reloaded = pabt_gates.load_schedule_data(path=path)
            self.assertEqual(reloaded["routes"]["123"][0]["gate"], "211")

    def test_build_sections_uses_hardcoded_without_scrape(self):
        now = datetime.datetime(2026, 8, 3, 4, 12)
        data = pabt_gates.builtin_schedule_payload()
        sections = pabt_gates.build_pabt_gates_sections(
            now=now,
            data=data,
            scrape=False,
        )
        self.assertEqual(len(sections), 1)
        self.assertTrue(sections[0]["title"].startswith(pabt_gates.SECTION_CURRENT))
        gates = sections[0]["boards"]
        self.assertEqual(gates[0]["trains"][0]["eta"], "Gate 80")
        self.assertNotIn("line", gates[0]["trains"][0])
        self.assertEqual(gates[1]["trains"][0]["eta"], "Gate 79")
        self.assertEqual(gates[2]["trains"][0]["eta"], "Gate 79")

    def test_format_schedule_updated_at(self):
        now = datetime.datetime(2026, 8, 3, 4, 30)
        self.assertEqual(
            pabt_gates.format_schedule_updated_at("2026-08-03T04:12:00", now=now),
            "4:12 AM",
        )
        self.assertEqual(
            pabt_gates.format_schedule_updated_at("2026-08-02T22:05:00", now=now),
            "Aug 2, 10:05 PM",
        )
        self.assertIsNone(pabt_gates.format_schedule_updated_at("builtin", now=now))
        self.assertEqual(
            pabt_gates.build_pabt_gates_sections(
                now=now,
                data={
                    "updated_at": "2026-08-03T04:12:00",
                    "routes": pabt_gates.builtin_schedule_payload()["routes"],
                },
            )[0]["title"],
            "Gates now · 4:12 AM",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
