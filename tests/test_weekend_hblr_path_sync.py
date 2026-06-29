# -*- coding: utf-8 -*-
"""Weekend HBLR branch timing and PATH arrival sync tests."""

import datetime
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import hblr_schedule, path_schedule  # noqa: E402

# PANYNJ lineColor for Newark-WTC (used only in tests, not app logic).
PATH_NEWARK_LINE_COLOR = "D93A30"
PATH_HOBOKEN_LINE_COLOR = "65C100"


def _is_wtc_headsign(headsign):
    text = (headsign or "").casefold()
    return "world trade" in text or text.strip() == "wtc"


def _exchange_wtc_arrivals_from_panynj(payload, newark_line_only=False):
    """Test helper: WTC-bound ToNY arrivals at Exchange Place."""
    arrivals = []
    for result in payload.get("results") or []:
        if result.get("consideredStation") != "EXP":
            continue
        for dest in result.get("destinations") or []:
            if (dest.get("label") or "").upper().replace(" ", "") != "TONY":
                continue
            for msg in dest.get("messages") or []:
                headsign = msg.get("headSign") or "?"
                if not _is_wtc_headsign(headsign):
                    continue
                line_color = (msg.get("lineColor") or "").upper().replace("#", "")
                if newark_line_only and line_color != PATH_NEWARK_LINE_COLOR:
                    continue
                match = re.search(r"(\d+)", msg.get("arrivalTimeMessage") or "")
                minutes = int(match.group(1)) if match else None
                arrivals.append({"minutes": minutes, "line_color": line_color})
    arrivals.sort(key=lambda item: item.get("minutes") if item.get("minutes") is not None else 9999)
    return arrivals


class WeekendHblrBranchStaggerTests(unittest.TestCase):
    """West Side Av departs 5 min after 8th St (toward Liberty State Pk area)."""

    LAG = 5
    STATIONS = ("Newport", "Exchange Place")
    WEEKEND_DAYS = (
        datetime.datetime(2026, 6, 27, 12, 0),
        datetime.datetime(2026, 6, 28, 12, 0),
    )

    def test_west_side_five_minutes_after_eighth_street(self):
        for day in self.WEEKEND_DAYS:
            for station in self.STATIONS:
                lines = hblr_schedule.branch_departures_in_weekend_window(station, day)
                eighth = lines["8th St"]
                west = lines["West Side Av"]
                self.assertGreaterEqual(len(eighth), 2, msg=station)
                self.assertGreaterEqual(len(west), len(eighth), msg=station)
                for eighth_time in eighth:
                    self.assertIn(
                        eighth_time + self.LAG,
                        west,
                        msg="%s %s: no West Side +%s after 8th at %s"
                        % (day.strftime("%a"), station, self.LAG, eighth_time),
                    )
                for index in range(min(len(eighth), len(west))):
                    if west[index] - eighth[index] == self.LAG:
                        continue
                    # lists may include extra West Side-only slots before the first 8th St
                    self.assertIn(eighth[index] + self.LAG, west)


class WeekendPathHblrSyncTests(unittest.TestCase):
    WEEKEND_DAYS = (
        datetime.datetime(2026, 6, 27, 12, 0),
        datetime.datetime(2026, 6, 28, 12, 0),
    )

    def test_path_33rd_newport_every_ten_minutes(self):
        for day in self.WEEKEND_DAYS:
            path = path_schedule.weekend_path_33rd_newport_offsets(day)
            self.assertGreater(len(path), 10)
            gaps = [path[i + 1] - path[i] for i in range(len(path) - 1)]
            self.assertTrue(all(gap == path_schedule.WEEKEND_PATH_33RD_HEADWAY for gap in gaps))
            self.assertLessEqual(path[-1], path_schedule.WEEKEND_PATH_33RD_NEWPORT_END)
            self.assertGreaterEqual(path[0], 0)

    def test_path_33rd_syncs_with_west_side_hblr_at_newport(self):
        """Every 10 min PATH; every other arrival aligns with 20 min West Side HBLR."""
        for day in self.WEEKEND_DAYS:
            west = hblr_schedule.branch_departures_in_weekend_window("Newport", day).get(
                "West Side Av", []
            )
            west_in_window = [
                offset
                for offset in west
                if offset <= path_schedule.WEEKEND_PATH_33RD_NEWPORT_END
            ]
            path = path_schedule.weekend_path_33rd_newport_offsets(day)
            for west_time in west_in_window:
                self.assertIn(
                    west_time,
                    path,
                    msg="West Side HBLR at %s should match a PATH 33rd arrival" % west_time,
                )
            synced = [path_time for path_time in path if path_time in west_in_window]
            self.assertEqual(
                len(synced),
                len(west_in_window),
                msg="each West Side departure should have a matching PATH arrival",
            )
            self.assertGreater(len(path), len(synced))

    def test_path_newark_wtc_exchange_every_twenty_minutes(self):
        for day in self.WEEKEND_DAYS:
            path = path_schedule.weekend_path_newark_wtc_exchange_offsets(day)
            self.assertGreater(len(path), 5)
            gaps = [path[i + 1] - path[i] for i in range(len(path) - 1)]
            self.assertTrue(
                all(gap == path_schedule.WEEKEND_PATH_NEWARK_WTC_HEADWAY for gap in gaps)
            )
            self.assertLessEqual(path[-1], path_schedule.WEEKEND_PATH_NEWARK_WTC_EXCHANGE_END)

    def test_path_newark_wtc_syncs_with_eighth_street_hblr_at_exchange(self):
        """PATH Newark-line WTC arrivals match 8th St HBLR departures at Exchange Place."""
        for day in self.WEEKEND_DAYS:
            eighth = hblr_schedule.branch_departures_in_weekend_window(
                "Exchange Place", day
            ).get("8th St", [])
            eighth_in_window = [
                offset
                for offset in eighth
                if offset <= path_schedule.WEEKEND_PATH_NEWARK_WTC_EXCHANGE_END
            ]
            path = path_schedule.weekend_path_newark_wtc_exchange_offsets(day)
            self.assertEqual(path, eighth_in_window)

    def test_exchange_wtc_filter_keeps_newark_line_only(self):
        """Hoboken-line WTC arrivals at Exchange Place are excluded from sync model."""
        payload = {
            "results": [
                {
                    "consideredStation": "EXP",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "headSign": "World Trade Center",
                                    "arrivalTimeMessage": "11 min",
                                    "lineColor": PATH_HOBOKEN_LINE_COLOR,
                                },
                                {
                                    "headSign": "World Trade Center",
                                    "arrivalTimeMessage": "20 min",
                                    "lineColor": PATH_NEWARK_LINE_COLOR,
                                },
                            ],
                        }
                    ],
                }
            ]
        }
        all_wtc = _exchange_wtc_arrivals_from_panynj(payload)
        newark_wtc = _exchange_wtc_arrivals_from_panynj(payload, newark_line_only=True)
        self.assertEqual(len(all_wtc), 2)
        self.assertEqual(len(newark_wtc), 1)
        self.assertEqual(newark_wtc[0]["minutes"], 20)
        self.assertEqual(newark_wtc[0]["line_color"], PATH_NEWARK_LINE_COLOR)


if __name__ == "__main__":
    unittest.main(verbosity=2)
