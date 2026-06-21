#!python3
"""Remote refresh coordination via LAN debug server."""

from __future__ import annotations

import os

from . import log_paths

CONTROL_REFRESH = "refresh"


def clear_control() -> None:
    try:
        os.remove(log_paths.control_file_path())
    except OSError:
        pass


def request_refresh() -> None:
    log_paths.ensure_log_dirs()
    log_paths._atomic_write(
        log_paths.control_file_path(),
        (CONTROL_REFRESH + "\n").encode("utf-8"),
    )


def is_refresh_requested() -> bool:
    return _read_control() == CONTROL_REFRESH


def _read_control() -> str:
    return log_paths.read_text_file(log_paths.control_file_path()).strip()
