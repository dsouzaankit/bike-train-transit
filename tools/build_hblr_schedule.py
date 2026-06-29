#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse NJ Transit HBLR PDF timetable into lib/hblr_schedule_data.json.

PC-only build step (requires pymupdf). The iPhone app reads the JSON at runtime.

The NJT PDF has four timetable blocks per page (left/right × top/bottom):
  - Left columns (8th St → West Side → … → Newport): north toward Hoboken/Tonnelle
  - Right columns (Newport → … → West Side → 8th St): south toward Bayonne branches

Usage:
    python tools/build_hblr_schedule.py
    python tools/build_hblr_schedule.py --pdf path/to/hblr.pdf --out lib/hblr_schedule_data.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

HBLR_PDF_URL = (
    "https://content.njtransit.com/sites/default/files/pdfs/rail/2025/07/10002/hblr.pdf"
)
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lib",
    "hblr_schedule_data.json",
)

TIME_RE = re.compile(r"^\d{3,4}$")

# x-centers measured from the 2025-07 NJT PDF (page width ~1230pt).
DIRECTION_COLUMNS = {
    "north_to_hoboken": (
        ("8th Street", 210.0),
        ("West Side Ave", 308.0),
        ("Liberty State Park", 357.0),
        ("Exchange Place", 422.0),
        ("Newport", 470.0),
    ),
    "south_to_bayonne": (
        ("Newport", 756.0),
        ("Exchange Place", 805.0),
        ("Liberty State Park", 874.0),
        ("West Side Ave", 918.0),
        ("8th Street", 1015.0),
    ),
}

STATIONS = (
    "8th Street",
    "West Side Ave",
    "Liberty State Park",
    "Exchange Place",
    "Newport",
)


def parse_time_token(text: str) -> int | None:
    """Parse NJT clock-face token (HMM / HHMM) to minutes from midnight."""
    if not TIME_RE.match(text):
        return None
    value = int(text)
    if value < 100 or value >= 2400:
        return None
    hour, minute = divmod(value, 100)
    if hour >= 24 or minute >= 60:
        return None
    return hour * 60 + minute


def _page_service_key(page) -> str:
    text = page.get_text("text").upper()
    if "SATURDAY" in text or "SUNDAY" in text:
        return "weekend"
    return "weekday"


def _time_bands(page_index: int, page_height: float) -> list[tuple[float, float]]:
    """Vertical ranges for the top and bottom timetable blocks on each page."""
    mid = page_height * 0.5
    if page_index == 0:
        return [(330.0, mid - 50.0), (mid + 50.0, 1630.0)]
    return [(120.0, mid - 50.0), (mid + 50.0, 1830.0)]


def _extract_column_times(
    words,
    station_x: float,
    y_min: float,
    y_max: float,
    tolerance: float = 8.0,
) -> list[int]:
    times: set[int] = set()
    for word in words:
        x0, y0, x1, y1, text, _block, _line, _wno = word
        if y0 < y_min or y0 > y_max:
            continue
        if not TIME_RE.match(text):
            continue
        cx = (x0 + x1) / 2.0
        if abs(cx - station_x) > tolerance:
            continue
        minute = parse_time_token(text)
        if minute is not None:
            times.add(minute)
    return sorted(times)


def parse_hblr_pdf(path: str) -> dict:
    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise SystemExit("Install pymupdf on the PC: pip install pymupdf") from exc

    doc = fitz.open(path)
    schedule: dict[str, dict[str, dict[str, list[int]]]] = {
        direction: {name: {} for name in STATIONS}
        for direction in DIRECTION_COLUMNS
    }

    for page_index in range(doc.page_count):
        page = doc[page_index]
        service_key = _page_service_key(page)
        words = page.get_text("words")
        page_height = page.rect.height

        for y_min, y_max in _time_bands(page_index, page_height):
            for direction, columns in DIRECTION_COLUMNS.items():
                for station, station_x in columns:
                    departures = _extract_column_times(
                        words,
                        station_x,
                        y_min,
                        y_max,
                    )
                    if not departures:
                        continue
                    bucket = schedule[direction][station]
                    existing = set(bucket.get(service_key, []))
                    existing.update(departures)
                    bucket[service_key] = sorted(existing)

    doc.close()

    for direction in DIRECTION_COLUMNS:
        for station in STATIONS:
            for service_key in ("weekday", "weekend"):
                schedule[direction][station].setdefault(service_key, [])

    return {
        "source_url": HBLR_PDF_URL,
        "directions": schedule,
        "notes": (
            "Parsed from NJT HBLR PDF. north_to_hoboken = left columns "
            "(8th Street, West Side Ave, Liberty State Park, Exchange Place, "
            "Newport). south_to_bayonne = right columns (Newport, Exchange Place, "
            "Liberty State Park, West Side Ave, 8th Street). "
            "Afternoon/evening gaps may be filled at runtime with headway "
            "estimates per the PDF footnote."
        ),
    }


def download_pdf(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "bike-train-transit/2.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    with open(dest, "wb") as fh:
        fh.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", help="Local HBLR PDF path (default: download from NJT)")
    parser.add_argument("--url", default=HBLR_PDF_URL, help="PDF URL when --pdf omitted")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path")
    args = parser.parse_args(argv)

    pdf_path = args.pdf
    temp_pdf = None
    if not pdf_path:
        import tempfile

        temp_pdf = os.path.join(tempfile.gettempdir(), "hblr_schedule.pdf")
        print("Downloading", args.url)
        download_pdf(args.url, temp_pdf)
        pdf_path = temp_pdf

    print("Parsing", pdf_path)
    data = parse_hblr_pdf(pdf_path)
    if temp_pdf:
        try:
            os.remove(temp_pdf)
        except OSError:
            pass

    for direction, stations in data["directions"].items():
        print(direction + ":")
        for station in STATIONS:
            for service_key in ("weekday", "weekend"):
                times = stations[station][service_key]
                sample = times[:4]
                print(f"  {station} {service_key}: {len(times)} departures (first {sample})")

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    print("Wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
