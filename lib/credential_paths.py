# -*- coding: utf-8 -*-
"""Where to look for gitignored API credential JSON on PC and Pythonista."""

from __future__ import annotations

import json
import os


def _safe_cwd() -> str | None:
    try:
        cwd = os.getcwd()
    except OSError:
        return None
    return cwd if isinstance(cwd, str) and cwd else None


def credential_roots() -> list[str]:
    """Project roots that may hold transit_credentials.json / njt_credentials.json."""
    roots: list[str] = []
    lib_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(lib_dir)
    candidates = [project_root, _safe_cwd()]
    try:
        from lib import log_paths

        candidates.append(log_paths.app_root())
    except Exception:
        pass
    for candidate in candidates:
        if isinstance(candidate, str) and candidate and candidate not in roots:
            roots.append(candidate)
    return roots


def load_json_credential(filename: str) -> dict | None:
    if not isinstance(filename, str) or not filename:
        return None
    for root in credential_roots():
        if not isinstance(root, str) or not root:
            continue
        try:
            path = os.path.join(root, filename)
        except TypeError:
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            continue
    return None
