# -*- coding: utf-8 -*-
"""Per-tab Citibike station lists, labels, and 2-column grid slots.

Each tab refreshes only its own station set into a separate snapshot cache.
"""

from __future__ import annotations

# --- Cbike JC (downtown) ---
STATIONS_JC = [
    "Dixon Mills",
    "Montgomery St",
    "Brunswick & 6th",
    "Monmouth & 6th",
    "Jersey & 6th St",
    "Newport PATH",
    "Washington St",
    "City Hall",
    "Grove St PATH",
    "Van Vorst Park",
    "Exchange Pl",
    "JC Medical Center",
    "Liberty Light Rail",
    "York St & Marin Blvd",
    "Marin Light Rail",
]
LABELS_JC = [
    "Dixon Mills",
    "Montgomery",
    "Brunswick",
    "Monmouth",
    "Jersey & 6th",
    "Newport PATH",
    "Washington St",
    "City Hall",
    "Grove St PATH",
    "Van Vorst\nPark",
    "Exchange Pl",
    "JC\nMedical Center",
    "Liberty\nLight Rail",
    "York St\n& Marin",
    "Marin\nLight Rail",
]
# Local indices 0–14
GRID_GROUPS_JC = [
    [(0, 1)],
    [(2, 3), (4, None)],
    [(5, 6)],
    [(7, 8)],
    [(9, 10)],
    [(13, 14)],
    [(11, 12)],
]

# --- Cbike S JC (south) ---
STATIONS_S_JC = [
    "Communipaw & Berry Lane",
    "Arlington Ave & Bramhall Ave",
    "Garfield Light Rail",
    "Carteret Ave & Arlington Ave",
    "Pacific Ave & Communipaw Ave",
    "Lafayette Park",
    "Dr. Lena Edwards Park",
    "MLK Dr & Bramhall Ave",
    "Astor Place",
]
LABELS_S_JC = [
    "Communipaw\n& Berry Ln",
    "Arlington\n& Bramhall",
    "Garfield\nLight Rail",
    "Carteret\n& Arlington",
    "Pacific\n& Communipaw",
    "Lafayette\nPark",
    "Lena Edwards\nPark",
    "MLK Dr\n& Bramhall",
    "Astor Place",
]
GRID_GROUPS_S_JC = [
    [(0, 1)],
    [(2, 3)],
    [(4, None)],
    [(5, 6)],
    [(7, 8)],
]

# --- Cbike HOB ---
STATIONS_HOB = [
    "Madison St & 10 St",
    "Adams St & 12 St",
    "Grand St & 14 St",
    "Willow Ave & 12 St",
    "14 St Ferry - 14 St & Shipyard Ln",
    "12 St & Sinatra Dr N",
]
LABELS_HOB = [
    "Madison\n& 10 St",
    "Adams\n& 12 St",
    "Grand\n& 14 St",
    "Willow\n& 12 St",
    "14 St Ferry",
    "Sinatra\nDr N",
]
GRID_GROUPS_HOB = [
    [(0, 1)],
    [(2, 3)],
    [(4, 5)],
]

# --- Cbike NYC (Hudson Yards / 11 Av) ---
STATIONS_NYC = [
    "12 Ave & W 40 St",
    "11 Ave & W 41 St",
    "W 44 St & 11 Ave",
    "W 52 St & 11 Ave",
    "W 54 St & 11 Ave",
]
LABELS_NYC = [
    "12 Ave\n& W 40",
    "11 Ave\n& W 41",
    "W 44\n& 11 Ave",
    "W 52\n& 11 Ave",
    "W 54\n& 11 Ave",
]
GRID_GROUPS_NYC = [
    [(0, 1)],
    [(2, 3)],
    [(4, None)],
]


def _build_grid_slots(groups):
    slots = []
    for row_pair in groups:
        for left, right in row_pair:
            slots.append(left)
            slots.append(right)
    return slots


# Union for CLI / email / logging station count.
STATIONS = STATIONS_JC + STATIONS_S_JC + STATIONS_HOB + STATIONS_NYC
STATION_LABELS = LABELS_JC + LABELS_S_JC + LABELS_HOB + LABELS_NYC

CBIKE_TAB_CONFIG = {
    "cbike_jc": {
        "stations": STATIONS_JC,
        "labels": LABELS_JC,
        "slots": _build_grid_slots(GRID_GROUPS_JC),
        "region": "JC",
        "cache_key": "snapshots_jc",
        "pill": "Cbike JC",
    },
    "cbike_s": {
        "stations": STATIONS_S_JC,
        "labels": LABELS_S_JC,
        "slots": _build_grid_slots(GRID_GROUPS_S_JC),
        "region": "JC",
        "cache_key": "snapshots_s",
        "pill": "Cbike S JC",
    },
    "cbike_hob": {
        "stations": STATIONS_HOB,
        "labels": LABELS_HOB,
        "slots": _build_grid_slots(GRID_GROUPS_HOB),
        "region": "HOB",
        "cache_key": "snapshots_hob",
        "pill": "Cbike HOB",
    },
    "cbike_nyc": {
        "stations": STATIONS_NYC,
        "labels": LABELS_NYC,
        "slots": _build_grid_slots(GRID_GROUPS_NYC),
        "region": "NYC",
        "cache_key": "snapshots_nyc",
        "pill": "Cbike NYC",
    },
}

CBIKE_TAB_KEYS = tuple(CBIKE_TAB_CONFIG.keys())
