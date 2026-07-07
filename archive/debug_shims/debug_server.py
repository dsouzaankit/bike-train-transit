#!python3
"""ARCHIVED — use: python bike_train_transit.py --safe"""

import os
import sys

_ARCHIVE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_ARCHIVE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _ARCHIVE not in sys.path:
    sys.path.insert(0, _ARCHIVE)

from debug_legacy import deprecate, run_bike_train_transit

deprecate("debug_server.py", "bike_train_transit.py --safe")

_argv = ["--safe"]
if "--port" in sys.argv:
    idx = sys.argv.index("--port")
    if idx + 1 < len(sys.argv):
        _argv.extend(["--port", sys.argv[idx + 1]])
elif "-p" in sys.argv:
    idx = sys.argv.index("-p")
    if idx + 1 < len(sys.argv):
        _argv.extend(["--port", sys.argv[idx + 1]])

run_bike_train_transit(_argv)
