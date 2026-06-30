#!python3
"""Copy app to On This iPhone so URL cold-start works (Files Downloads does not)."""

from __future__ import annotations

import os
import shutil

LOCAL_DIR_NAME = "bike_train_transit"
MAIN_SCRIPT = "bike_train_transit.py"
# Copied to On This iPhone on deploy (shortcut runs from Documents, not the edit folder).
CREDENTIAL_FILES = (
    "transit_credentials.json",
    ".transit_credentials.json",
    "njt_credentials.json",
    ".njt_credentials.json",
)


def local_app_dir() -> str:
    return os.path.join(os.path.expanduser("~/Documents"), LOCAL_DIR_NAME)


def _file_sig(path: str) -> tuple[float, int] | None:
    try:
        st = os.stat(path)
        return (st.st_mtime, st.st_size)
    except OSError:
        return None


def _needs_copy(src: str, dst: str) -> bool:
    if not os.path.isfile(dst):
        return True
    return _file_sig(src) != _file_sig(dst)


def _sync_tree(src: str, dst: str) -> None:
    """Copy only new or changed files (no rmtree — safe if interrupted)."""
    if not os.path.isdir(src):
        return
    os.makedirs(dst, exist_ok=True)
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        dst_root = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(dst_root, exist_ok=True)
        for name in files:
            s = os.path.join(root, name)
            d = os.path.join(dst_root, name)
            if _needs_copy(s, d):
                shutil.copy2(s, d)


def deploy_local_app(source_dir: str) -> str:
    """Mirror main script + lib/ into Pythonista Documents for shortcut launch."""
    source_dir = os.path.abspath(source_dir)
    dest = local_app_dir()
    os.makedirs(dest, exist_ok=True)

    src_main = os.path.join(source_dir, MAIN_SCRIPT)
    if not os.path.isfile(src_main):
        raise FileNotFoundError("Missing %s in %s" % (MAIN_SCRIPT, source_dir))

    dst_main = os.path.join(dest, MAIN_SCRIPT)
    if _needs_copy(src_main, dst_main):
        shutil.copy2(src_main, dst_main)

    src_lib = os.path.join(source_dir, "lib")
    dst_lib = os.path.join(dest, "lib")
    if os.path.isdir(src_lib):
        _sync_tree(src_lib, dst_lib)

    for name in CREDENTIAL_FILES:
        src = os.path.join(source_dir, name)
        dst = os.path.join(dest, name)
        if os.path.isfile(src) and _needs_copy(src, dst):
            shutil.copy2(src, dst)

    for name in (
        "debug_server.py",
        "debug_citibike_inactive.py",
        "debug_path_inactive.py",
        "debug_subway_inactive.py",
        "debug_hblr_inactive.py",
    ):
        src = os.path.join(source_dir, name)
        dst = os.path.join(dest, name)
        if os.path.isfile(src) and _needs_copy(src, dst):
            shutil.copy2(src, dst)

    return dest


def deploy_status(source_dir: str) -> str:
    dest = deploy_local_app(source_dir)
    return "Deployed for shortcut: %s" % dest
