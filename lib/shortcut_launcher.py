#!python3
"""Install RunBikeTrainTransit.py launcher on On This iPhone (SOCKS-style)."""

from __future__ import annotations

import os
import sys

from . import local_deploy

LAUNCHER_NAME = "RunBikeTrainTransit.py"
UI_SCRIPT_REL = "bike_train_transit/bike_train_transit.py"
_STALE_LAUNCHER_NAMES = (
    "citibike_refresh.py",
    "Run Citibike Refresh.py",
    "RunCitibikeRefresh.py",
    "citibike_refresh_pythonista.py",
)
LAUNCHER_VERSION = 9
URL_LAUNCH_ENV = "BIKE_TRAIN_TRANSIT_URL_LAUNCH"

_LAUNCHER_TEMPLATE = '''#!/usr/bin/env python3
"""Launch Bike Train Transit app (auto-generated; do not edit)."""
# launcher-version: {version}
import os
import runpy
import sys

_APP_DIR = os.path.join(os.path.expanduser("~/Documents"), "bike_train_transit")
_DEPLOYED_MAIN = os.path.join(_APP_DIR, "bike_train_transit.py")


def _run_app():
    if _APP_DIR not in sys.path:
        sys.path.insert(0, _APP_DIR)
    runpy.run_path(_DEPLOYED_MAIN, run_name="__main__")


if __name__ == "__main__":
    if not os.path.isfile(_DEPLOYED_MAIN):
        print("Main script not found:", _DEPLOYED_MAIN, flush=True)
        print("Run bike_train_transit.py once in Pythonista to deploy.", flush=True)
        raise SystemExit(1)
    print("Starting Bike Train Transit from", _DEPLOYED_MAIN, flush=True)
    # Do NOT raise SystemExit after this: the app presents its UI non-blocking
    # and schedules background work. Exiting the launcher script tears down the
    # presented view and ui.in_background threads, crashing Pythonista. Letting
    # the launcher fall through keeps the UI alive, same as a direct Run.
    _run_app()
'''


def _is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def _local_library_dir() -> str:
    return os.path.expanduser("~/Documents")


def _launcher_path() -> str:
    return os.path.join(_local_library_dir(), LAUNCHER_NAME)


def deployed_main_path() -> str:
    return os.path.join(local_deploy.local_app_dir(), local_deploy.MAIN_SCRIPT)


def shortcuts_run_url() -> str:
    try:
        import shortcuts

        return shortcuts.pythonista_url(LAUNCHER_NAME, action="run")
    except ImportError:
        return "pythonista3://%s?action=run" % LAUNCHER_NAME


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
    if not _is_pythonista():
        return None
    _remove_stale_launchers()
    source_dir = os.path.abspath(app_dir or os.path.dirname(os.path.dirname(__file__)))
    _resolve_launcher_app_dir(source_dir)
    body = _LAUNCHER_TEMPLATE.format(version=LAUNCHER_VERSION)
    path = _launcher_path()
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
    except OSError as exc:
        print("Could not install launcher %s: %s" % (path, exc), flush=True)
        return None
    return path


def launcher_help_lines(app_dir: str | None = None, install: bool = True) -> list[str]:
    source_dir = os.path.abspath(app_dir or os.path.dirname(os.path.dirname(__file__)))
    installed = install_launcher(source_dir) if install else None
    if not install:
        path = _launcher_path()
        installed = path if os.path.isfile(path) else None
    url = shortcuts_run_url()
    run_dir = local_deploy.local_app_dir() if _is_pythonista() else source_dir
    lines = [
        "",
        "=== iOS Shortcut (launcher v%s) ===" % LAUNCHER_VERSION,
        "URL: %s" % url,
        "",
        "IMPORTANT (same as SOCKS proxy):",
        "Files -> iCloud -> Downloads is NOT runnable via URL.",
        "App is copied to On This iPhone on each run:",
        "  %s" % run_dir,
        "",
        "1. Run bike_train_transit.py once in Pythonista",
        "2. Shortcuts -> Open URLs -> paste URL above",
        "3. Add to Home Screen",
        "Launcher: On This iPhone -> %s" % LAUNCHER_NAME,
        "",
        "Launcher runs the app in-process (runpy); no URL re-launch.",
        "Alternative: Pythonista wrench -> Add to Home Screen.",
    ]
    if installed:
        lines.append("Installed: %s" % installed)
    if source_dir != run_dir:
        lines.append("Edit source: %s" % source_dir)
    lines.extend(
        [
            "After editing in Downloads, run once again to redeploy.",
            "===================================",
            "",
        ]
    )
    return lines
