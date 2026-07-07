#!python3
"""Deploy the app to On This iPhone and report the Home Screen launch URL.

The Home Screen icon must target the UI script directly (run as the main
script). A RunBikeTrainTransit.py launcher stub does NOT work for this app:
launching it via runpy runs the app nested and breaks Pythonista's UI run
loop (ui.in_background never fires, refresh hangs). The stub is removed if
present.
"""

from __future__ import annotations

import os
import sys

from . import local_deploy

LAUNCHER_NAME = "RunBikeTrainTransit.py"
UI_SCRIPT_REL = "bike_train_transit/bike_train_transit.py"
SAFE_SCRIPT_REL = "bike_train_transit/debug_server.py"
# Obsolete launcher scripts deleted from On This iPhone on each run. The
# RunBikeTrainTransit.py stub is included: it breaks UI launch (see module docstring).
_STALE_LAUNCHER_NAMES = (
    "citibike_refresh.py",
    "Run Citibike Refresh.py",
    "RunCitibikeRefresh.py",
    "citibike_refresh_pythonista.py",
    LAUNCHER_NAME,
)
LAUNCHER_VERSION = 10
URL_LAUNCH_ENV = "BIKE_TRAIN_TRANSIT_URL_LAUNCH"


def _is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def _local_library_dir() -> str:
    return os.path.expanduser("~/Documents")


def deployed_main_path() -> str:
    return os.path.join(local_deploy.local_app_dir(), local_deploy.MAIN_SCRIPT)


def shortcuts_run_url() -> str:
    """Direct URL to the deployed UI script (runs as the main script)."""
    try:
        import shortcuts

        return shortcuts.pythonista_url(UI_SCRIPT_REL, action="run")
    except ImportError:
        return "pythonista3://%s?action=run" % UI_SCRIPT_REL


def shortcuts_safe_mode_url() -> str:
    """Direct URL to safe mode (LAN logs only, no UI)."""
    try:
        import shortcuts

        return shortcuts.pythonista_url(SAFE_SCRIPT_REL, action="run")
    except ImportError:
        return "pythonista3://%s?action=run" % SAFE_SCRIPT_REL


def handoff_to_ui_app() -> bool:
    """Re-open the UI script in full Pythonista (not Shortcuts extension context)."""
    if not _is_pythonista():
        return False
    if not os.path.isfile(deployed_main_path()):
        print(
            "Deploy missing — run bike_train_transit.py once in Pythonista first.",
            flush=True,
        )
        return False
    try:
        import shortcuts

        url = shortcuts.pythonista_url(UI_SCRIPT_REL, action="run")
        shortcuts.open_url(url)
        return True
    except Exception as exc:
        print("UI handoff failed: %s" % exc, flush=True)
        return False


def _remove_stale_launchers() -> None:
    for name in _STALE_LAUNCHER_NAMES:
        path = os.path.join(_local_library_dir(), name)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def _resolve_launcher_app_dir(source_dir: str) -> str:
    """Shortcut must run from On This iPhone, not Files -> Downloads."""
    if not _is_pythonista():
        return os.path.abspath(source_dir)
    try:
        return local_deploy.deploy_local_app(source_dir)
    except KeyboardInterrupt:
        print("Local deploy interrupted — using existing copy if present", flush=True)
        dest = local_deploy.local_app_dir()
        if os.path.isfile(os.path.join(dest, local_deploy.MAIN_SCRIPT)):
            return dest
        return os.path.abspath(source_dir)
    except OSError as exc:
        print("Local deploy failed: %s" % exc, flush=True)
        return os.path.abspath(source_dir)


def install_launcher(app_dir: str | None = None) -> str | None:
    """Deploy the app to On This iPhone and remove the obsolete launcher stub.

    No launcher stub is written: the Home Screen targets the UI script directly.
    """
    if not _is_pythonista():
        return None
    _remove_stale_launchers()
    source_dir = os.path.abspath(app_dir or os.path.dirname(os.path.dirname(__file__)))
    _resolve_launcher_app_dir(source_dir)
    return deployed_main_path()


def launcher_help_lines(app_dir: str | None = None, install: bool = True) -> list[str]:
    source_dir = os.path.abspath(app_dir or os.path.dirname(os.path.dirname(__file__)))
    if install:
        install_launcher(source_dir)
    url = shortcuts_run_url()
    safe_url = shortcuts_safe_mode_url()
    run_dir = local_deploy.local_app_dir() if _is_pythonista() else source_dir
    lines = [
        "",
        "=== iOS Home Screen (run as main script) ===",
        "URL: %s" % url,
        "",
        "=== Safe mode (LAN logs only, after a crash) ===",
        "URL: %s" % safe_url,
        "Or run debug_server.py in Pythonista (same as bike_train_transit.py --safe)",
        "",
        "Runs from On This iPhone (Files -> iCloud Downloads is NOT URL-runnable):",
        "  %s" % run_dir,
        "",
        "1. Run bike_train_transit.py once in Pythonista (deploys to Documents)",
        "2. Shortcuts -> + -> URL action (paste URL) -> Open URLs action",
        "3. Turn off Show in Share Sheet -> Add to Home Screen",
        "",
        "Point the icon at bike_train_transit.py directly (runs as main script).",
        "Do NOT use a RunBikeTrainTransit.py stub: runpy launch breaks the UI loop.",
    ]
    if source_dir != run_dir:
        lines.append("Edit source: %s" % source_dir)
    lines.extend(
        [
            "After editing in Downloads, run once again to redeploy.",
            "============================================",
            "",
        ]
    )
    return lines
