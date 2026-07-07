#!python3
"""ARCHIVED — use: python bike_train_transit.py --inactive citibike"""

import os
import sys

_ARCHIVE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_ARCHIVE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _ARCHIVE not in sys.path:
    sys.path.insert(0, _ARCHIVE)

from debug_legacy import deprecate, run_bike_train_transit

deprecate("debug_citibike_inactive.py", "bike_train_transit.py --inactive citibike")
run_bike_train_transit(["--inactive", "citibike"])
