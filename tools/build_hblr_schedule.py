#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse NJ Transit HBLR PDF timetable into lib/hblr_schedule_data.json.

PC-only build step (requires pymupdf). The iPhone app reads the JSON at runtime.

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
from collections import defaultdict

HBLR_PDF_URL = (
    "https://content.njtransit.com/sites/default/files/pdfs/rail/2025/07/10002/hblr.pdf"
)
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lib",
    "hblr_schedule_data.json",
)

STATIONS = ("Newport", "Exchange Place")
TIME_RE = re.compile(r"^\d{3,4}$")


def parse_time_token(text: str) -> int | None:
    """Parse NJT clock-face token (HMM / HHMM) to minutes from midnight."""
    if not TIME_RE.match(text):
        return None
    value = int(text)
    if value < 100:
        return None
    if value >= 2400:
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


def _find_south_station_columns(page) -> dict[str, float]:
    """Return x-centers for Newport / Exchange Place in the southbound table."""
    words = page.get_text("words")
    width = page.rect.width
    height = page.rect.height
    midpoint = width * 0.52
    header_y_max = height * 0.55

    newport_points: list[tuple[float, float]] = []
    by_block_line: dict[tuple, list] = defaultdict(list)
    for word in words:
        x0, y0, x1, y1, text, block, line, _wno = word
        cx = (x0 + x1) / 2.0
        if y0 > header_y_max:
            continue
        if text == "Newport" and cx > midpoint:
            newport_points.append((cx, y0))
        if text in ("Exchange", "Place"):
            by_block_line[(block, line)].append((x0, text, y0, cx))

    columns: dict[str, float] = {}
    if not newport_points:
        return columns

    newport_x = round(sum(cx for cx, _y in newport_points) / len(newport_points), 1)
    header_y = sum(y for _cx, y in newport_points) / len(newport_points)
    columns["Newport"] = newport_x

    best_exchange: tuple[float, float] | None = None
    for _key, parts in by_block_line.items():
        parts.sort(key=lambda item: item[0])
        name = " ".join(text for _x, text, _y, _cx in parts)
        if "Exchange" not in name:
            continue
        ys = [y for _x, _text, y, _cx in parts]
        xs = [cx for _x, _text, _y, cx in parts]
        avg_y = sum(ys) / len(ys)
        avg_x = sum(xs) / len(xs)
        if abs(avg_y - header_y) > 30:
            continue
        if avg_x <= newport_x or avg_x > newport_x + 90:
            continue
        if avg_x > width * 0.88:
            continue
        if best_exchange is None or abs(avg_x - (newport_x + 48)) < abs(
            best_exchange[0] - (newport_x + 48)
        ):
            best_exchange = (avg_x, avg_y)

    if best_exchange is not None:
        columns["Exchange Place"] = round(best_exchange[0], 1)

    return columns


def _extract_column_times(page, station_x: float, header_y_max: float = 220.0) -> list[int]:
    words = page.get_text("words")
    times: set[int] = set()
    for word in words:
        x0, y0, x1, y1, text, _block, _line, _wno = word
        if y0 < header_y_max:
            continue
        if not TIME_RE.match(text):
            continue
        cx = (x0 + x1) / 2.0
        if abs(cx - station_x) > 8.0:
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
    schedule: dict[str, dict[str, list[int]]] = {name: {} for name in STATIONS}

    for page_index in range(doc.page_count):
        page = doc[page_index]
        service_key = _page_service_key(page)
        columns = _find_south_station_columns(page)
        if not columns:
            continue

        # Page 1 weekend headers sit lower than page 2 weekday headers.
        header_y_max = 400.0 if page_index == 0 else 220.0

        for station, station_x in columns.items():
            departures = _extract_column_times(page, station_x, header_y_max=header_y_max)
            if not departures:
                continue
            existing = set(schedule[station].get(service_key, []))
            existing.update(departures)
            schedule[station][service_key] = sorted(existing)

    doc.close()

    for station in STATIONS:
        for service_key in ("weekday", "weekend"):
            schedule[station].setdefault(service_key, [])

    return {
        "source_url": HBLR_PDF_URL,
        "direction": "south_to_bayonne",
        "stations": schedule,
        "notes": (
            "Southbound departures toward 8th St / West Side Ave at Newport and "
            "Exchange Place. Parsed from NJT PDF; afternoon/evening gaps may be "
            "filled at runtime with headway estimates per the PDF footnote."
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

    for station in STATIONS:
        for service_key in ("weekday", "weekend"):
            count = len(data["stations"][station][service_key])
            sample = data["stations"][station][service_key][:4]
            print(f"  {station} {service_key}: {count} departures (first {sample})")

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
