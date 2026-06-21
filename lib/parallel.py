"""Parallel helpers compatible with Pythonista (stdlib ThreadPoolExecutor is broken there)."""
import threading
import time


def run_parallel(tasks, timeout=None):
    """Run {name: callable()} in daemon threads; return {name: result or None}."""
    results = {}
    lock = threading.Lock()

    def worker(name, fn, _results=results, _lock=lock):
        try:
            val = fn()
        except Exception:
            val = None
        with _lock:
            _results[name] = val

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
    """Apply fn(item) to each item in parallel; preserve input order."""
    if not items:
        return []
    tasks = {"{}".format(i): (lambda item=item: fn(item)) for i, item in enumerate(items)}
    out = run_parallel(tasks, timeout=timeout)
    return [out.get("{}".format(i)) for i in range(len(items))]
