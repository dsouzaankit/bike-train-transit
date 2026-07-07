# -*- coding: utf-8 -*-
"""Archived helper for deprecated root-level debug_*.py shims."""

from __future__ import annotations

import os
import runpy
import sys


def _app_root() -> str:
    # archive/debug_shims/ → project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def deprecate(legacy_script: str, replacement: str) -> None:
    print(
        "DEPRECATED: %s — use %s instead" % (legacy_script, replacement),
        flush=True,
    )


def run_bike_train_transit(extra_argv):
    """Run bike_train_transit.main() with extra CLI args after the script name."""
    root = _app_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    argv = [os.path.join(root, "bike_train_transit.py")]
    argv.extend(extra_argv or [])
    saved = sys.argv
    try:
        sys.argv = argv
        runpy.run_path(argv[0], run_name="__main__")
    finally:
        sys.argv = saved
