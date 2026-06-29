# -*- coding: utf-8 -*-
"""Capture Transit App HBLR stop_departures fixtures for PDF sync tests.

Usage (PC, with transit_credentials.json):
  python tools/capture_transit_hblr_fixtures.py

Re-run when NJT updates the HBLR PDF or to refresh reference snapshots.
Respects API rate limit (5 req/min): ~13s between stops.
"""

from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from hblr_transit_reference import (  # noqa: E402
    FIXTURE_DIR,
    LIVE_HBLR_BOARDS,
    MANIFEST_PATH,
    fixture_path,
    transit_stop_id,
)
from lib import transit_app  # noqa: E402

CAPTURE_DELAY_SEC = 13


def main():
    if not transit_app.has_api_key():
        raise SystemExit("Transit API key missing — add transit_credentials.json first.")

    os.makedirs(FIXTURE_DIR, exist_ok=True)
    captured_at = int(time.time())
    manifest_fixtures = []

    for index, spec in enumerate(LIVE_HBLR_BOARDS):
        if index:
            time.sleep(CAPTURE_DELAY_SEC)
        stop_id = transit_stop_id(spec["station"])
        if not stop_id:
            raise SystemExit("No transit_stop_id for %s" % spec["station"])

        transit_app.clear_departure_cache()
        payload = transit_app.fetch_stop_departures(stop_id, max_departures=10)

        record = {
            "id": spec["id"],
            "station": spec["station"],
            "direction": spec["direction"],
            "global_stop_id": stop_id,
            "captured_at": captured_at,
            "payload": payload,
        }
        path = fixture_path(spec["id"])
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")
        manifest_fixtures.append(
            {
                "id": spec["id"],
                "station": spec["station"],
                "direction": spec["direction"],
                "global_stop_id": stop_id,
                "captured_at": captured_at,
                "file": os.path.basename(path),
            }
        )
        print("wrote", path)

    manifest = {
        "version": 1,
        "captured_at": captured_at,
        "fixtures": manifest_fixtures,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print("wrote", MANIFEST_PATH)


if __name__ == "__main__":
    main()
