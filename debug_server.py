#!python3
# Safe mode: LAN log server only (no Bike Train Transit UI). Run after a crash to read persisted logs.
#
#   python debug_server.py
#   python debug_server.py --port 8765
#   python bike_train_transit.py --safe
#
# Open from PC: http://<phone-ip>:8765/

import asyncio
import sys

LISTEN_HOST = "0.0.0.0"
LAN_DEBUG_PORT = 8765


def _parse_port() -> int:
    for i, arg in enumerate(sys.argv):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return LAN_DEBUG_PORT


def run_safe_mode(port: int | None = None) -> None:
    from lib.file_logging import setup_safe_mode_logging
    from lib.lan_debug_server import run_lan_debug_server
    from lib.log_paths import ensure_log_dirs

    port = LAN_DEBUG_PORT if port is None else port
    ensure_log_dirs()
    setup_safe_mode_logging(port)
    print("Safe mode — LAN log server only (no Bike Train Transit UI)", flush=True)
    print("Log dir:", ensure_log_dirs(), flush=True)
    print("Open http://<phone-ip>:{}/".format(port), flush=True)
    try:
        asyncio.run(run_lan_debug_server(LISTEN_HOST, port, safe_mode=True))
    except KeyboardInterrupt:
        print("Stopped.", flush=True)


if __name__ == "__main__":
    run_safe_mode(_parse_port())
