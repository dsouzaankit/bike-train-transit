#!python3
# Minimal LAN HTTP server for Bike Train Transit log files (full app mode + safe mode).

import json
import os
import urllib.parse
from typing import Callable, Optional

from . import log_paths

StatusFn = Callable[[], dict]

_active_debug_server = None
_active_debug_loop = None

HTML_HEAD = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Bike Train Transit Debug</title>
<style>
body{font-family:-apple-system,sans-serif;margin:16px;background:#111;color:#ddd}
a{color:#8cf} pre{background:#222;padding:12px;overflow:auto;max-height:70vh;font-size:12px}
.btn{display:inline-block;margin:8px 8px 8px 0;padding:8px 14px;background:#333;color:#eee;
border-radius:6px;text-decoration:none;border:1px solid #555}
.warn{color:#f96}.ok{color:#8f8}
</style></head><body>
"""


def _http_response(
    status: int,
    reason: str,
    headers: dict[str, str],
    body: bytes,
) -> bytes:
    lines = ["HTTP/1.1 {} {}".format(status, reason)]
    headers = dict(headers)
    if "Content-Length" not in headers:
        headers["Content-Length"] = str(len(body))
    if "Connection" not in headers:
        headers["Connection"] = "close"
    for key, value in headers.items():
        lines.append("{}: {}".format(key, value))
    lines.append("")
    return "\r\n".join(lines).encode("ascii") + b"\r\n" + body


def _parse_request(raw: bytes) -> tuple[str, str]:
    try:
        line = raw.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        parts = line.split()
        if len(parts) >= 2:
            return parts[0].upper(), parts[1].split("?", 1)[0]
    except Exception:
        pass
    return "GET", "/"


def _log_path_aliases() -> dict[str, str]:
    latest = log_paths.latest_log_path()
    progress = log_paths.progress_log_path()
    ok = log_paths.ok_probe_path()
    crash = log_paths.crash_marker_path()
    return {
        "/" + log_paths.LATEST_LOG: latest,
        "/citibike_latest.txt": latest,
        "/export_latest.txt": latest,
        "/proxy_latest.txt": latest,
        "/" + log_paths.PROGRESS_LOG: progress,
        "/citibike_progress.txt": progress,
        "/export_progress.txt": progress,
        "/proxy_progress.txt": progress,
        "/" + log_paths.OK_PROBE: ok,
        "/citibike_ok.txt": ok,
        "/proxy_ok.txt": ok,
        "/" + log_paths.CRASH_MARKER: crash,
        "/citibike_crash.txt": crash,
        "/proxy_crash.txt": crash,
    }


def _safe_log_path(url_path: str) -> Optional[str]:
    """Map URL path to a file under log_dir; reject traversal."""
    root = os.path.realpath(log_paths.log_dir())
    aliases = _log_path_aliases()
    if url_path in aliases:
        path = aliases[url_path]
    elif url_path.startswith("/logs/"):
        name = urllib.parse.unquote(url_path[len("/logs/") :])
        if not name or "/" in name or "\\" in name or name.startswith("."):
            return None
        path = os.path.join(log_paths.log_dir(), name)
    else:
        return None
    real = os.path.realpath(path)
    if not real.startswith(root + os.sep) and real != root:
        return None
    return real


def _minimal_index_html(safe_mode: bool) -> bytes:
    crash = log_paths.read_text_file(log_paths.crash_marker_path())
    latest = log_paths.read_text_file(log_paths.latest_log_path(), "(empty)")
    history = log_paths.list_history_logs(8)
    crash_html = ""
    if crash.strip():
        crash_html = (
            '<p class="warn"><b>Last crash marker:</b> '
            '<a href="/{}">{}</a></p>'.format(log_paths.CRASH_MARKER, log_paths.CRASH_MARKER)
            + "<h2>Crash marker</h2><pre>"
            + _html_escape(crash)
            + "</pre>"
        )
    mode = "safe mode (logs only)" if safe_mode else "full app"
    hist_links = " ".join(
        '<a href="/logs/{}">{}</a>'.format(h, h) for h in history
    ) or "<span>(none)</span>"
    pre_style = "max-height:85vh" if safe_mode else "max-height:70vh"
    prev_section = ""
    if safe_mode and history:
        prev_name = history[0]
        prev_path = os.path.join(log_paths.log_dir(), prev_name)
        prev_content = log_paths.read_text_file(prev_path, "")
        if prev_content.strip() and prev_content.strip() != latest.strip():
            prev_section = (
                "<h2>Previous session ({})</h2><pre style=\"{}\">".format(
                    prev_name, pre_style
                )
                + _html_escape(prev_content)
                + "</pre>"
            )
    safe_note = ""
    if safe_mode:
        safe_note = (
            "<p class='warn'>Safe mode preserves existing logs. "
            "Console output is now captured to the latest log.</p>"
        )
    body = (
        HTML_HEAD.replace("max-height:70vh", pre_style)
        + "<h1>Bike Train Transit Debug</h1>"
        + "<p class='ok'>LAN log server — {}</p>".format(mode)
        + safe_note
        + crash_html
        + "<p>"
        + '<a class="btn" href="/">Refresh</a>'
        + '<a class="btn" href="/{}">Latest log</a>'.format(log_paths.LATEST_LOG)
        + '<a class="btn" href="/{}">Progress (12 lines)</a>'.format(log_paths.PROGRESS_LOG)
        + '<a class="btn" href="/status.json">status.json</a>'
        + '<a class="btn" href="/refresh">Trigger refresh (LAN)</a>'
        + "</p>"
        + "<h2>Latest log</h2><pre>"
        + _html_escape(latest)
        + "</pre>"
        + prev_section
        + "<h2>History</h2><p>"
        + hist_links
        + "</p></body></html>"
    )
    return body.encode("utf-8")


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _status_json(safe_mode: bool, status_fn: Optional[StatusFn]) -> bytes:
    payload = {
        "mode": "safe" if safe_mode else "full",
        "logDir": log_paths.log_dir(),
        "latestLog": "/" + log_paths.LATEST_LOG,
        "progressLog": "/" + log_paths.PROGRESS_LOG,
        "okProbe": "/" + log_paths.OK_PROBE,
        "crashMarker": log_paths.read_text_file(log_paths.crash_marker_path()).strip()
        or None,
        "historyLogs": [
            "/logs/{}".format(n) for n in log_paths.list_history_logs(20)
        ],
    }
    if status_fn is not None:
        try:
            payload["app"] = status_fn()
        except Exception as exc:
            payload["appError"] = str(exc)
    return json.dumps(payload, indent=2).encode("utf-8")


async def _safe_close_writer(writer) -> None:
    try:
        if not writer.is_closing():
            writer.close()
            await writer.wait_closed()
    except Exception:
        pass


async def _serve_request(
    reader,
    writer,
    safe_mode: bool = False,
    status_fn: Optional[StatusFn] = None,
) -> None:
    try:
        raw = await reader.read(16384)
        method, path = _parse_request(raw)
        if method not in ("GET", "HEAD"):
            body = b"Method not allowed\n"
            writer.write(
                _http_response(405, "Method Not Allowed", {"Content-Type": "text/plain"}, body)
            )
            await writer.drain()
            return

        if path == "/status.json":
            body = _status_json(safe_mode, status_fn)
            if method == "HEAD":
                body = b""
            writer.write(
                _http_response(
                    200,
                    "OK",
                    {"Content-Type": "application/json; charset=utf-8"},
                    body,
                )
            )
            await writer.drain()
            return

        if path == "/refresh":
            try:
                from .app_control import request_refresh

                request_refresh()
            except Exception:
                pass
            body = json.dumps({"status": "refresh requested"}).encode("utf-8")
            if method == "HEAD":
                body = b""
            writer.write(
                _http_response(
                    200,
                    "OK",
                    {"Content-Type": "application/json; charset=utf-8"},
                    body,
                )
            )
            await writer.drain()
            return

        if path in ("/", "/browse"):
            body = _minimal_index_html(safe_mode)
            if method == "HEAD":
                body = b""
            writer.write(
                _http_response(
                    200,
                    "OK",
                    {"Content-Type": "text/html; charset=utf-8"},
                    body,
                )
            )
            await writer.drain()
            return

        file_path = _safe_log_path(path)
        if file_path is None or not os.path.isfile(file_path):
            body = b"Not found\n"
            writer.write(
                _http_response(404, "Not Found", {"Content-Type": "text/plain"}, body)
            )
            await writer.drain()
            return

        with open(file_path, "rb") as fh:
            data = fh.read()
        if method == "HEAD":
            data = b""
        writer.write(
            _http_response(
                200,
                "OK",
                {"Content-Type": "text/plain; charset=utf-8"},
                data,
            )
        )
        await writer.drain()
    except Exception:
        pass
    finally:
        await _safe_close_writer(writer)


async def run_lan_debug_server(
    listen_host: str,
    listen_port: int,
    safe_mode: bool = False,
    status_fn: Optional[StatusFn] = None,
) -> None:
    import asyncio

    global _active_debug_server, _active_debug_loop

    async def client_connected(reader, writer) -> None:
        await _serve_request(
            reader,
            writer,
            safe_mode=safe_mode,
            status_fn=status_fn,
        )

    server = await asyncio.start_server(
        client_connected,
        host=listen_host,
        port=listen_port,
        reuse_address=True,
    )
    _active_debug_loop = asyncio.get_running_loop()
    _active_debug_server = server
    mode = "safe" if safe_mode else "full"
    log_paths.ensure_log_dirs()
    try:
        from .file_logging import get_file_writer

        w = get_file_writer()
        if w:
            w.log("LAN debug server {} on {}:{}".format(mode, listen_host, listen_port))
    except ImportError:
        pass
    async with server:
        await server.serve_forever()
    _active_debug_server = None


def stop_lan_debug_server() -> None:
    server = _active_debug_server
    loop = _active_debug_loop
    if server is None or loop is None:
        return

    def _close() -> None:
        if not server.is_serving():
            return
        server.close()

    try:
        loop.call_soon_threadsafe(_close)
    except RuntimeError:
        _close()


def start_lan_debug_server_thread(
    listen_host: str,
    listen_port: int,
    safe_mode: bool = False,
    status_fn: Optional[StatusFn] = None,
) -> None:
    """Own thread + event loop — survives main app crashes."""
    import threading

    def _run() -> None:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                run_lan_debug_server(
                    listen_host,
                    listen_port,
                    safe_mode,
                    status_fn,
                )
            )
        except Exception:
            pass
        finally:
            try:
                loop.close()
            except Exception:
                pass

    thread = threading.Thread(target=_run, name="bike-train-transit-lan-debug", daemon=True)
    thread.start()
