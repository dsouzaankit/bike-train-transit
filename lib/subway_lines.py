# -*- coding: utf-8 -*-
"""NYC subway line badge colors (MTA service bullet palette)."""

from __future__ import annotations

# Official MTA line colors — https://new.mta.info/agency/new-york-city-transit
SUBWAY_LINE_COLORS = {
    "1": "#EE352E",
    "2": "#EE352E",
    "3": "#EE352E",
    "4": "#00933C",
    "5": "#00933C",
    "6": "#00933C",
    "7": "#B933AD",
    "A": "#0039A6",
    "C": "#0039A6",
    "E": "#0039A6",
    "B": "#FF6319",
    "D": "#FF6319",
    "F": "#FF6319",
    "M": "#FF6319",
    "G": "#6CBE45",
    "J": "#996633",
    "Z": "#996633",
    "L": "#A7A9AC",
    "N": "#FCCC0A",
    "Q": "#FCCC0A",
    "R": "#FCCC0A",
    "W": "#FCCC0A",
    "S": "#808183",
    "GS": "#808183",
    "H": "#808183",
    "FS": "#808183",
    "SI": "#0039A6",
}

# Lines that use dark text on the badge (yellow / light green).
_DARK_TEXT_LINES = frozenset({"N", "Q", "R", "W", "G"})

_LINE_SORT_ORDER = "1234567ABCDEFGJLMNQRSWZ"


def normalize_line(line) -> str:
    if line in (None, ""):
        return "?"
    return str(line).strip().upper()


def subway_line_color(line) -> str:
    key = normalize_line(line)
    return SUBWAY_LINE_COLORS.get(key, "#5A6A7A")


def subway_line_text_color(line) -> str:
    key = normalize_line(line)
    return "#000000" if key in _DARK_TEXT_LINES else "#FFFFFF"


def line_sort_key(line) -> tuple:
    key = normalize_line(line)
    if key in _LINE_SORT_ORDER:
        return (0, _LINE_SORT_ORDER.index(key))
    return (1, key)
