#!python3
"""Bike Train Transit — Subway inactive (no subway API boards)."""

import os
import runpy
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ["BIKE_TRAIN_TRANSIT_INACTIVE"] = "subway"
runpy.run_path(os.path.join(_ROOT, "bike_train_transit.py"), run_name="__main__")
