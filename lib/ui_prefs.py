# -*- coding: utf-8 -*-
"""Persistent UI preferences (thumb-float handedness, etc.)."""

from __future__ import annotations

import json
import os
import tempfile

HANDEDNESS_LHD = "lhd"
HANDEDNESS_RHD = "rhd"
DEFAULT_HANDEDNESS = HANDEDNESS_LHD
_PREFS_NAME = "ui_prefs.json"


def _prefs_path() -> str:
    from . import log_paths

    return os.path.join(log_paths.app_root(), _PREFS_NAME)


def normalize_handedness(value) -> str:
    text = str(value or "").strip().casefold()
    if text in (HANDEDNESS_RHD, "right", "right-handed", "r"):
        return HANDEDNESS_RHD
    return HANDEDNESS_LHD


def load_prefs(*, path: str | None = None) -> dict:
    data_path = path or _prefs_path()
    try:
        with open(data_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            return raw
    except (OSError, ValueError, TypeError):
        pass
    return {}


def save_prefs(prefs: dict, *, path: str | None = None) -> str:
    data_path = path or _prefs_path()
    os.makedirs(os.path.dirname(data_path) or ".", exist_ok=True)
    payload = dict(prefs or {})
    # Atomic-ish replace for Pythonista / PC.
    directory = os.path.dirname(data_path) or "."
    fd, tmp = tempfile.mkstemp(prefix="ui_prefs_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, data_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return data_path


def get_thumb_float_handedness(*, path: str | None = None) -> str:
    prefs = load_prefs(path=path)
    return normalize_handedness(prefs.get("thumb_float_handedness"))


def set_thumb_float_handedness(handedness: str, *, path: str | None = None) -> str:
    prefs = load_prefs(path=path)
    prefs["thumb_float_handedness"] = normalize_handedness(handedness)
    save_prefs(prefs, path=path)
    return prefs["thumb_float_handedness"]


def toggle_thumb_float_handedness(*, path: str | None = None) -> str:
    current = get_thumb_float_handedness(path=path)
    nxt = HANDEDNESS_RHD if current == HANDEDNESS_LHD else HANDEDNESS_LHD
    return set_thumb_float_handedness(nxt, path=path)
