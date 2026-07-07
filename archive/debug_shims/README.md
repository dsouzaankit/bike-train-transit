# Deprecated debug shims (archived)

Root **`debug_server.py`** is kept — it is the one-tap safe-mode entry for Pythonista
(equivalent to `bike_train_transit.py --safe`).

These **`debug_*_inactive.py`** scripts were removed from the project root. They only
printed a deprecation warning and forwarded to `bike_train_transit.py` CLI flags.

Update Pythonista shortcuts to run **`bike_train_transit.py`** with the flags below.

| Archived script | Use instead |
|-----------------|-------------|
| `debug_citibike_inactive.py` | `bike_train_transit.py --inactive citibike` |
| `debug_path_inactive.py` | `bike_train_transit.py --inactive path` |
| `debug_subway_inactive.py` | `bike_train_transit.py --inactive subway` |
| `debug_hblr_inactive.py` | `bike_train_transit.py --inactive hblr` |

Not deployed to the phone (`deploy.ps1` excludes `archive/`).
