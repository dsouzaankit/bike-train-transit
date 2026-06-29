# -*- coding: utf-8 -*-
"""Offline weekend PATH arrival schedules (aligned with HBLR branch phases)."""

from __future__ import annotations

import datetime

# Continuous minutes from Saturday/Sunday noon.
WEEKEND_PATH_33RD_NEWPORT_END = 9 * 60  # 12:00–21:00
WEEKEND_PATH_NEWARK_WTC_EXCHANGE_END = 11 * 60  # 12:00–23:00
WEEKEND_PATH_33RD_HEADWAY = 10
WEEKEND_PATH_NEWARK_WTC_HEADWAY = 20
PATH_HBLR_SYNC_TOLERANCE = 1


def _is_weekend(when: datetime.datetime) -> bool:
    return when.weekday() >= 5


def weekend_path_33rd_newport_offsets(
    when: datetime.datetime | None = None,
) -> list[int]:
    """PATH 33rd-bound arrivals at Newport every 10 min (12:00–21:00 weekend)."""
    from lib.hblr_schedule import branch_departures_in_weekend_window

    when = when or datetime.datetime.now()
    if not _is_weekend(when):
        return []
    west = branch_departures_in_weekend_window("Newport", when).get("West Side Av", [])
    in_window = [offset for offset in west if offset <= WEEKEND_PATH_33RD_NEWPORT_END]
    phase = in_window[0] if in_window else 5
    return list(range(phase, WEEKEND_PATH_33RD_NEWPORT_END + 1, WEEKEND_PATH_33RD_HEADWAY))


def weekend_path_newark_wtc_exchange_offsets(
    when: datetime.datetime | None = None,
) -> list[int]:
    """PATH Newark-line WTC-bound arrivals at Exchange Place every 20 min (12:00–23:00)."""
    from lib.hblr_schedule import branch_departures_in_weekend_window

    when = when or datetime.datetime.now()
    if not _is_weekend(when):
        return []
    eighth = branch_departures_in_weekend_window("Exchange Place", when).get("8th St", [])
    return [offset for offset in eighth if offset <= WEEKEND_PATH_NEWARK_WTC_EXCHANGE_END]
