#!python3
"""Shared app state for UI, CLI, and LAN debug status (survives runpy / ui.delay)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

_state: dict[str, Any] = {
    "busy": False,
    "stationCount": 0,
    "lastRefresh": None,
    "lastError": None,
    "stations": [],
    "pathTrains": [],
    "path33rdTrains": [],
    "pathNjTrains": [],
    "subwayTrains": [],
    "subwayToJcTrains": [],
    "activeTab": "from_jc",
}


def snapshot() -> dict[str, Any]:
    return dict(_state)


def set_busy(busy: bool) -> None:
    _state["busy"] = busy


def set_error(message: str | None) -> None:
    _state["lastError"] = message


def set_active_tab(tab: str) -> None:
    _state["activeTab"] = tab


def update_refresh(
    snapshots,
    path_boards=None,
    subway_boards=None,
    path_33rd_boards=None,
    path_nj_boards=None,
    subway_to_jc_boards=None,
    active_tab="from_jc",
    *,
    tagged_name_fn,
) -> None:
    _state["stationCount"] = len(snapshots)
    _state["lastRefresh"] = datetime.now().isoformat(timespec="seconds")
    _state["lastError"] = None
    _state["activeTab"] = active_tab
    _state["stations"] = [
        {
            "region": s["region"],
            "name": tagged_name_fn(s),
            "bikes": s["bikes"],
            "docks": s["docks"],
        }
        for s in snapshots
    ]
    _state["pathTrains"] = path_boards or []
    _state["path33rdTrains"] = path_33rd_boards or []
    _state["pathNjTrains"] = path_nj_boards or []
    _state["subwayTrains"] = subway_boards or []
    _state["subwayToJcTrains"] = subway_to_jc_boards or []


def update_cli(
    snapshots,
    path_boards,
    subway_boards,
    path_33rd_boards=None,
    path_nj_boards=None,
    subway_to_jc_boards=None,
    *,
    tagged_name_fn,
) -> None:
    update_refresh(
        snapshots,
        path_boards,
        subway_boards,
        path_33rd_boards,
        path_nj_boards,
        subway_to_jc_boards,
        active_tab="from_jc",
        tagged_name_fn=tagged_name_fn,
    )
