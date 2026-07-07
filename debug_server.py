#!python3
"""One-tap safe mode — LAN log server only (no UI).

Pythonista Home Screen URL:
  pythonista3://bike_train_transit/debug_server.py?action=run

Equivalent to: bike_train_transit.py --safe
"""

from __future__ import annotations

import os
import runpy
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

DEFAULT_PORT = 8765


def _parse_port(default: int = DEFAULT_PORT) -> int:
    argv = sys.argv[1:]
    for flag in ("--port", "-p"):
        if flag in argv:
            idx = argv.index(flag)
            if idx + 1 < len(argv):
                try:
                    return int(argv[idx + 1])
                except ValueError:
                    pass
    return default


def main() -> None:
    app_root = _ROOT
    try:
        from lib import local_deploy

        app_root = local_deploy.deploy_local_app(_ROOT)
    except Exception as exc:
        print("Deploy skipped: %s" % exc, flush=True)

    port = _parse_port()
    argv = [
        os.path.join(app_root, "bike_train_transit.py"),
        "--safe",
        "--port",
        str(port),
    ]
    saved = sys.argv
    try:
        sys.argv = argv
        runpy.run_path(argv[0], run_name="__main__")
    finally:
        sys.argv = saved


if __name__ == "__main__":
    main()
