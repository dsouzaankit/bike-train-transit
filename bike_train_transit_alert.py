#!/usr/bin/env python3
"""Fetch Citibike dock counts for selected stations and send a Bike Train Transit email alert."""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

GBFS_BASE = "https://gbfs.citibikenyc.com/gbfs/en"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
DEFAULT_ENV = SCRIPT_DIR / ".env"


@dataclass
class StationSnapshot:
    station_id: str
    name: str
    bikes_available: int
    docks_available: int
    total_capacity: int
    is_renting: bool
    is_returning: bool
    last_reported: int | None

    @property
    def fill_pct(self) -> float | None:
        if self.total_capacity <= 0:
            return None
        return round(100 * self.bikes_available / self.total_capacity, 1)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "bike-train-transit-alert/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_station_ids(config: dict[str, Any]) -> list[str]:
    stations = config.get("stations", [])
    if not stations:
        raise ValueError("config.json must include a non-empty 'stations' list")
    if len(stations) > 24:
        raise ValueError("This script is configured for up to 24 stations")
    return [str(station) for station in stations]


def build_station_lookup() -> tuple[dict[str, str], dict[str, str]]:
    info_payload = fetch_json(f"{GBFS_BASE}/station_information.json")
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for station in info_payload["data"]["stations"]:
        station_id = str(station["station_id"])
        name = station["name"]
        by_id[station_id] = name
        by_name[name.casefold()] = station_id
        if "legacy_id" in station:
            by_id[str(station["legacy_id"])] = name
    return by_id, by_name


def normalize_station_id(raw: str, by_id: dict[str, str], by_name: dict[str, str]) -> str:
    if raw in by_id:
        return raw
    matched = by_name.get(raw.casefold())
    if matched:
        return matched
    raise ValueError(f"Unknown station '{raw}'. Use --list-stations to find IDs or exact names.")


def get_station_snapshots(config: dict[str, Any]) -> list[StationSnapshot]:
    by_id, by_name = build_station_lookup()
    configured = resolve_station_ids(config)
    station_ids = [normalize_station_id(item, by_id, by_name) for item in configured]

    status_payload = fetch_json(f"{GBFS_BASE}/station_status.json")
    status_by_id = {
        str(station["station_id"]): station for station in status_payload["data"]["stations"]
    }

    snapshots: list[StationSnapshot] = []
    for station_id in station_ids:
        status = status_by_id.get(station_id)
        if status is None:
            raise ValueError(f"No live status found for station {station_id}")

        bikes = int(status.get("num_bikes_available", 0))
        docks = int(status.get("num_docks_available", 0))
        snapshots.append(
            StationSnapshot(
                station_id=station_id,
                name=by_id.get(station_id, station_id),
                bikes_available=bikes,
                docks_available=docks,
                total_capacity=bikes + docks,
                is_renting=bool(status.get("is_renting", 0)),
                is_returning=bool(status.get("is_returning", 0)),
                last_reported=status.get("last_reported"),
            )
        )
    return snapshots


def should_alert(snapshot: StationSnapshot, config: dict[str, Any]) -> list[str]:
    alerts: list[str] = []
    min_bikes = int(config.get("alert_min_bikes", 0))
    min_docks = int(config.get("alert_min_docks", 0))

    if min_bikes and snapshot.bikes_available <= min_bikes:
        alerts.append(f"bikes low ({snapshot.bikes_available} <= {min_bikes})")
    if min_docks and snapshot.docks_available <= min_docks:
        alerts.append(f"empty docks low ({snapshot.docks_available} <= {min_docks})")
    return alerts


def format_report(snapshots: list[StationSnapshot], config: dict[str, Any]) -> tuple[str, str, bool]:
    now = datetime.now(timezone.utc).astimezone()
    region = config.get("region")
    region_tag = f" [{region}]" if region else ""
    station_prefix = f"[{region}] " if region else ""
    lines = [
        f"Bike Train Transit — Citibike dock status{region_tag}",
        f"Checked at: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
    ]

    alert_hits: list[str] = []
    for snapshot in snapshots:
        fill = "n/a" if snapshot.fill_pct is None else f"{snapshot.fill_pct}%"
        lines.extend(
            [
                f"{station_prefix}{snapshot.name}",
                f"  Station ID: {snapshot.station_id}",
                f"  Bikes available (filled): {snapshot.bikes_available}",
                f"  Empty docks available: {snapshot.docks_available}",
                f"  Total capacity: {snapshot.total_capacity}",
                f"  Fill level: {fill}",
                f"  Renting: {'yes' if snapshot.is_renting else 'no'} | Returning: {'yes' if snapshot.is_returning else 'no'}",
                "",
            ]
        )
        station_alerts = should_alert(snapshot, config)
        if station_alerts:
            alert_hits.append(f"{station_prefix}{snapshot.name}: {', '.join(station_alerts)}")

    send_on_ok = bool(config.get("email_always", True))
    if alert_hits:
        lines.extend(["ALERTS:", *[f"- {item}" for item in alert_hits], ""])
        subject = f"Bike Train Transit alert: {len(alert_hits)} station(s) need attention"
        return subject, "\n".join(lines), True

    subject = "Bike Train Transit: all watched stations OK"
    return subject, "\n".join(lines), send_on_ok


def send_email(subject: str, body: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.mail.yahoo.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    email_from = os.environ.get("EMAIL_FROM", smtp_user)
    email_to = os.environ.get("EMAIL_TO", smtp_user)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_from
    message["To"] = email_to
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def list_stations(limit: int = 25) -> None:
    payload = fetch_json(f"{GBFS_BASE}/station_information.json")
    stations = payload["data"]["stations"][:limit]
    for station in stations:
        legacy = station.get("legacy_id", "")
        suffix = f" (legacy {legacy})" if legacy else ""
        print(f"{station['station_id']}: {station['name']}{suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to config.json with station list and alert thresholds",
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=DEFAULT_ENV,
        help="Path to .env file with SMTP credentials",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the email body without sending",
    )
    parser.add_argument(
        "--list-stations",
        action="store_true",
        help="Print sample station IDs/names and exit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env)

    if args.list_stations:
        list_stations()
        return 0

    config = load_config(args.config)
    snapshots = get_station_snapshots(config)
    subject, body, should_send = format_report(snapshots, config)

    print(body)
    print("")

    if args.dry_run:
        print("Dry run: email not sent.")
        return 0

    if not should_send:
        print("No alert thresholds hit and email_always=false; email not sent.")
        return 0

    missing = [name for name in ("SMTP_USER", "SMTP_PASSWORD") if not os.environ.get(name)]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    try:
        send_email(subject, body)
    except (smtplib.SMTPException, OSError, KeyError) as exc:
        print(f"Failed to send email: {exc}", file=sys.stderr)
        return 1

    print(f"Email sent: {subject}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"Failed to reach Citibike API: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
