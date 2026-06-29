# -*- coding: utf-8 -*-
"""Where to look for gitignored API credential JSON on PC and Pythonista."""

from __future__ import annotations

import json
import os


def credential_roots() -> list[str]:
    """Project roots that may hold transit_credentials.json / njt_credentials.json."""
    roots: list[str] = []
    lib_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(lib_dir)
    for candidate in (project_root, os.getcwd()):
        if candidate and candidate not in roots:
            roots.append(candidate)
    try:
        from lib import log_paths

        app_root = log_paths.app_root()
        if app_root not in roots:
            roots.append(app_root)
    except Exception:
        pass
    return roots


def load_json_credential(filename: str) -> dict | None:
    for root in credential_roots():
        path = os.path.join(root, filename)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            continue
    return None
