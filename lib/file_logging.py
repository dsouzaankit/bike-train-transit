#!python3
# File logging — atomic latest log + session history.

import logging
import sys
import threading
import traceback
from typing import Optional

from . import log_paths

_file_writer: Optional["FileLogWriter"] = None
_tee_installed = False
_original_stdout = None
_original_stderr = None


class FileLogWriter:
    """Writes ISO8601 lines to bike_train_transit_latest.txt and the current session file."""

    def __init__(self, session_path: str, initial_lines: list[str] | None = None):
        self._session_path = session_path
        self._lock = threading.Lock()
        self._lines: list[str] = list(initial_lines or [])

    def log_line(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)
            body = "".join(self._lines).encode("utf-8")
            log_paths._atomic_write(log_paths.latest_log_path(), body)
            log_paths._atomic_write(self._session_path, body)
            tail = self._lines[-12:]
            log_paths._atomic_write(
                log_paths.progress_log_path(),
                "".join(tail).encode("utf-8"),
            )

    def log(self, message: str) -> None:
        self.log_line("{} {}\n".format(log_paths._iso_now(), message))


class FileLogHandler(logging.Handler):
    def __init__(self, writer: FileLogWriter, level: int = logging.NOTSET):
        super().__init__(level)
        self._writer = writer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._writer.log_line(
                "{} [{}] {}\n".format(
                    log_paths._iso_now(),
                    record.levelname,
                    msg,
                )
            )
        except Exception:
            pass


class TeeStream:
    """Mirror stdout/stderr to the log file (console errors visible over LAN)."""

    def __init__(self, stream, label: str):
        self._stream = stream
        self._label = label

    def write(self, data):
        if self._stream is not None and data:
            try:
                self._stream.write(data)
                self._stream.flush()
            except Exception:
                pass
        if data:
            _capture_console_text(data, self._label)

    def flush(self):
        if self._stream is not None:
            try:
                self._stream.flush()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _capture_console_text(data, label: str) -> None:
    text = data if isinstance(data, str) else data.decode("utf-8", errors="replace")
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        message = "[{}] {}".format(label, line)
        writer = _file_writer
        if writer is not None:
            writer.log(message)
        else:
            append_to_latest(message)


def append_to_latest(message: str) -> None:
    """Append one line without resetting the log (safe mode / pre-session capture)."""
    log_paths.ensure_log_dirs()
    line = "{} {}\n".format(log_paths._iso_now(), message)
    path = log_paths.latest_log_path()
    existing = log_paths.read_text_file(path, "")
    body = existing + line
    log_paths._atomic_write(path, body.encode("utf-8"))
    lines = body.splitlines(keepends=True)
    log_paths._atomic_write(
        log_paths.progress_log_path(),
        "".join(lines[-12:]).encode("utf-8"),
    )


def _log_traceback(prefix: str, exc_type, exc, tb) -> None:
    writer = _file_writer
    msg = "".join(traceback.format_exception(exc_type, exc, tb))
    if writer is not None:
        writer.log(prefix)
        for line in msg.splitlines():
            writer.log(line)
        return
    append_to_latest(prefix)
    for line in msg.splitlines():
        append_to_latest(line)


def get_file_writer() -> Optional[FileLogWriter]:
    return _file_writer


def install_console_tee() -> None:
    global _tee_installed, _original_stdout, _original_stderr
    if _tee_installed:
        return
    _original_stdout = sys.stdout
    _original_stderr = sys.stderr
    sys.stdout = TeeStream(_original_stdout, "stdout")
    sys.stderr = TeeStream(_original_stderr, "stderr")
    _tee_installed = True


def install_thread_hook() -> None:
    if not hasattr(threading, "excepthook"):
        return

    def _thread_hook(args):
        _log_traceback(
            "FATAL thread {}:".format(args.thread.name if args.thread else "?"),
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        )
        if args.exc_value is not None:
            log_paths.write_crash_marker(args.exc_value)
        default = threading.__excepthook__
        if default is not None:
            default(args)

    threading.excepthook = _thread_hook


def install_crash_hooks() -> None:
    def _excepthook(exc_type, exc, tb):
        _log_traceback("FATAL uncaught exception:", exc_type, exc, tb)
        log_paths.write_crash_marker(exc)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook


def setup_file_logging(level: int = logging.INFO) -> FileLogWriter:
    global _file_writer
    log_paths.ensure_log_dirs()
    log_paths.prune_old_logs()
    log_paths.clear_crash_marker()
    session = log_paths.new_session_log_path()
    _file_writer = FileLogWriter(session)
    _file_writer.log("=== session {} ===".format(session))
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if isinstance(handler, FileLogHandler):
            root.removeHandler(handler)
    handler = FileLogHandler(_file_writer, level=level)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root.addHandler(handler)
    install_console_tee()
    install_thread_hook()
    install_crash_hooks()
    return _file_writer


def setup_safe_mode_logging(port: int = 8765) -> None:
    """Preserve crash logs; tee console; do not start a fresh session."""
    log_paths.ensure_log_dirs()
    log_paths.write_ok_probe(mode="safe")
    append_to_latest("=== safe mode LAN server on port {} ===".format(port))
    install_console_tee()
    install_thread_hook()
    install_crash_hooks()


def log_message(text: str) -> None:
    writer = _file_writer
    if writer is not None:
        writer.log(text)
    else:
        append_to_latest(text)


def log_banner(text: str) -> None:
    writer = _file_writer
    if writer is None:
        for line in text.splitlines():
            append_to_latest(line)
        return
    for line in text.splitlines():
        writer.log(line)


def log_crash(exc: BaseException) -> None:
    writer = _file_writer
    if writer is not None:
        writer.log("FATAL crash: {}: {}".format(type(exc).__name__, exc))
        writer.log(traceback.format_exc())
    else:
        append_to_latest("FATAL crash: {}: {}".format(type(exc).__name__, exc))
        append_to_latest(traceback.format_exc())
    log_paths.write_crash_marker(exc)
