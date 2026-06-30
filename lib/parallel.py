"""Parallel helpers compatible with Pythonista (stdlib ThreadPoolExecutor is broken there)."""
import sys
import threading
import time


def _is_pythonista() -> bool:
    return "Pythonista" in sys.executable


def run_parallel(tasks, timeout=None):
    """Run {name: callable()} in parallel on PC; sequential on Pythonista.

    Pythonista's embedded CPython can hard-crash (no traceback) when several
    threads run TLS/urllib at once, so transit fetches run one at a time there.
    """
    if _is_pythonista():
        results = {}
        for name, fn in tasks.items():
            try:
                results[name] = fn()
            except Exception:
                results[name] = None
        return {name: results.get(name) for name in tasks}

    results = {}
    lock = threading.Lock()

    def worker(name, fn):
        try:
            val = fn()
        except Exception:
            val = None
        with lock:
            results[name] = val

    threads = []
    for name, fn in tasks.items():
        t = threading.Thread(target=worker, args=(name, fn), daemon=True)
        t.start()
        threads.append(t)

    deadline = (time.time() + timeout) if timeout else None
    for t in threads:
        if deadline is not None:
            remaining = max(0.01, deadline - time.time())
            t.join(timeout=remaining)
        else:
            t.join()

    return {name: results.get(name) for name in tasks}


def map_parallel(items, fn, timeout=None):
    """Apply fn(item) to each item; sequential on Pythonista, parallel elsewhere."""
    if not items:
        return []
    tasks = {"{}".format(i): (lambda item=item: fn(item)) for i, item in enumerate(items)}
    out = run_parallel(tasks, timeout=timeout)
    return [out.get("{}".format(i)) for i in range(len(items))]
