# Bike Train Transit

Monitor Citibike dock counts, PATH trains, and NYC subway departures for Jersey City (`JC`) stations — plus a **To JC** tab for downtown subway and NJ-bound PATH from Manhattan. Includes an iPhone UI (Pythonista), optional PC email alerts, and a LAN debug server for reading logs from your desktop.

Uses the public [Citibike GBFS API](https://gbfs.citibikenyc.com/gbfs/en/) — no Citibike account login required.

## Features

- **Two tabs** — **From JC** (bikes + outbound transit) and **To JC** (inbound transit from Manhattan)
- **iPhone app** — compact 2-column grid showing filled bikes and empty docks for JC stations
- **PATH + subway connections** — From JC subway cards filter for trains reachable after PATH arrival + walk time (Christopher St +5 min, West 4 St +7 min)
- **PATH & subway** — real-time departures in grouped sections (see [App tabs](#app-tabs) below); PATH uses one PANYNJ fetch for all boards
- **Compact ETAs** — `5m`, `Due`, `Delay` / `~5m` (fits narrow card columns without ellipsis)
- **Low-count alerts** — cards highlight red when bikes or docks ≤ threshold
- **LAN debug server** — browse logs and status from a PC on the same Wi‑Fi (`:8765`)
- **PC deploy script** — `deploy.ps1` zips the project to iCloud Downloads for Pythonista sync
- **PC email script** — optional Yahoo SMTP status/alert emails
- **iOS Shortcut** — one-tap launch from Home Screen

## Jersey City stations (`JC`)

| | | |
|---|---|---|
| Dixon Mills | Montgomery St | Brunswick & 6th |
| Monmouth & 6th | Jersey & 6th St | Newport PATH |
| Washington St | City Hall | Grove St PATH |

All stations are tagged `[JC]` in logs, email, and the **From JC** tab title.

## App tabs

Tap **From JC** or **To JC** in the tab bar below the header. One refresh loads both tabs; switching tabs uses cached data (no extra network calls).

### From JC

| Section | Stations | Data |
|---------|----------|------|
| **Citibike grid** | 9 JC stations | GBFS bike/dock counts |
| **PATH → NYC** | Grove St PATH, Newport PATH | Next NYC-bound PATH trains |
| **PATH → 33rd St** | Christopher St, 9th St | Next 33rd St-bound PATH trains |
| **Subway → North / Queens** | Christopher St, West 4 St | Uptown/Queens departures **after PATH + walk** (note: “after PATH +5 min”) |

Bike cards appear first; transit sections load in parallel afterward. Refresh uses a **main-thread UI queue** and **cached station lookup** so repeat taps work reliably on Pythonista.

### To JC

| Section | Stations | Data |
|---------|----------|------|
| **Subway → South Ferry** | WTC Cortlandt, World Trade Center | Downtown 1 / E trains toward South Ferry / WTC |
| **PATH → NJ** | Christopher St, 9th St, 33rd St, World Trade Center | Next NJ-bound PATH trains (2×2 card grid) |

**World Trade Center subway:** uses direct E-line arrivals when available. If not, estimates from **Canal St** WTC-bound departures **+2 min** (shown with `~` and note “est. Canal St + 2 min”).

## Project layout

```
bike_train_transit/
  bike_train_transit.py           # iPhone UI (Pythonista)
  bike_train_transit_alert.py     # PC email script
  deploy.ps1                      # Zip + copy to iCloud Downloads (PC → iPhone)
  config.json                     # PC stations + thresholds
  debug_server.py                 # Safe mode: logs only (no UI)
  lib/
    path_trains.py                # PATH NYC / 33rd / NJ (PANYNJ single-fetch)
    subway_trains.py              # Subway north and To JC boards
    parallel.py                   # Pythonista-safe parallel fetch (not ThreadPoolExecutor)
    app_state.py                  # Shared state for UI / LAN status.json
    shortcut_launcher.py          # Launcher v7 (Shortcuts two-hop handoff)
    local_deploy.py               # Incremental copy to On This iPhone
    file_logging.py, log_paths.py # Session logs + safe-mode preservation
    lan_debug_server.py           # LAN debug HTTP server
  windows/                        # PC helpers for LAN debug URLs, deploy config
  .env.example                    # Yahoo SMTP template
```

## Requirements

- **Python 3** (stdlib only — no pip packages)
- **Pythonista 3** on iPhone for the UI
- iPhone and PC on the same Wi‑Fi for LAN debug
- **iCloud Drive** on Windows (for `deploy.ps1`)

---

## Deploy workflow (PC → iPhone via iCloud)

Use this when editing on Windows and syncing to Pythonista. Same pattern as [iOS-SOCKS-Server](../iOS-SOCKS-Server).

### 1. Force quit Pythonista on the iPhone

- Open the app switcher and swipe **Pythonista** away.

Force quit releases log files and the LAN debug listener. It is faster and more reliable than waiting for an in-app stop when redeploying.

### 2. Delete the old project folder in Files

On the iPhone, open **Files** and delete **`bike_train_transit`** wherever it exists:

- **iCloud Drive → Downloads** — remove the old extracted folder (not just the zip)
- **Pythonista** (iCloud or On My iPhone) — remove the copy you run from

Do this **after** force quitting Pythonista and **before** running `deploy.ps1` on the PC.

### 3. Run deploy on the PC

```powershell
cd P:\all_scripts\bike_train_transit
.\deploy.ps1
```

The script:

1. Removes old `bike_train_transit.zip` and `bike_train_transit\` from iCloud Downloads
2. Stages the project (excludes logs, `windows/`, PC-only email files, editor junk)
3. Creates `bike_train_transit.zip` and copies it to `%USERPROFILE%\iCloudDrive\Downloads`

Optional: set `iCloudDownloads` in `windows\bike-train-transit-windows.json` if your iCloud path differs.

### 4. Install on iPhone

1. **Files → iCloud Drive → Downloads**
2. Tap **`bike_train_transit.zip`** to unzip
3. Copy the **`bike_train_transit`** folder into Pythonista
4. Run **`bike_train_transit.py`** once

On first launch the app will:

- Show the **From JC** tab with bike grid and refresh live data
- Start the LAN debug server on port **8765**
- Copy itself to **On This iPhone → Documents/bike_train_transit/** (for URL launch)
- Install **`RunBikeTrainTransit.py`** on On This iPhone
- Log shortcut setup steps to the console and LAN log

Launcher deploy runs in the background so the UI opens immediately. Only changed files are copied on redeploy.

---

## iPhone setup (manual alternatives)

If you are not using `deploy.ps1`:

- **iCloud** — sync via Files / iCloud Drive (e.g. `Downloads/bike_train_transit/`)
- **Copy/paste** — paste `bike_train_transit.py` + `lib/` into Pythonista

Always copy the **entire folder including `lib/`**, not just the main script.

### Edit stations (optional)

In `bike_train_transit.py`, edit `STATIONS`, `STATION_LABELS`, `GRID_GROUPS`, and `REGION` at the top. Transit station lists live in `lib/path_trains.py` and `lib/subway_trains.py`.

---

## iOS Home Screen (one-tap launch)

The shortcut must target the **launcher stub** on **On This iPhone**, not the iCloud copy directly.

### Recommended: Pythonista wrench (most reliable)

The **Shortcuts app “Open URLs” action often fails to open Pythonista**. Use Pythonista’s built-in Home Screen flow instead:

1. Run `bike_train_transit.py` once in Pythonista (creates the launcher)
2. In Pythonista’s file browser, open **On This iPhone** → **`RunBikeTrainTransit.py`**
3. Tap the **wrench icon** → **Shortcuts…** → **Add to Home Screen**
4. Safari opens → **Share** → **Add to Home Screen**

### Test the URL first (Safari)

Paste this in **Safari’s address bar** (not Shortcuts):

```
pythonista3://RunBikeTrainTransit.py?action=run
```

If iOS asks **“Open in Pythonista?”** → tap **Allow**. If that works, the wrench method above will work too.

### Shortcuts app (fallback)

Only use this if the wrench method is not an option:

1. **Shortcuts** → **+** → **Open URLs** (not Text, not Get Contents of URL)
2. URL: `pythonista3://RunBikeTrainTransit.py?action=run`
3. Turn off **Show in Share Sheet** in shortcut settings
4. **⋯** → **Add to Home Screen**

If tapping the icon does nothing, switch to the **wrench method** above.

### Alternative URLs

If the launcher is not installed yet, use the iCloud path (adjust folder if needed):

```
pythonista3://iCloud/Downloads/bike_train_transit/bike_train_transit.py?action=run&root=icloud
```

### Shortcut help in logs

Each UI launch logs shortcut setup steps to:

- Pythonista console (`>_` button)
- LAN log: `http://<phone-ip>:8765/bike_train_transit_latest.txt`

---

## LAN debug server

Runs on the **iPhone** (not PC). Your PC reads logs over Wi‑Fi.

| URL | Description |
|-----|-------------|
| `http://<phone-ip>:8765/` | HTML dashboard with live log tail |
| `/bike_train_transit_latest.txt` | Full session log |
| `/bike_train_transit_progress.txt` | Last 12 log lines |
| `/status.json` | App state (stations, transit boards, active tab, errors) |
| `/refresh` | Trigger refresh on the phone from PC |

Legacy aliases `/citibike_*.txt` still work.

Find your iPhone IP: **Settings → Wi‑Fi → (i) → IP Address**

Example: `http://10.0.100.10:8765/`

Console output (`stdout`/`stderr`), thread tracebacks, and crash markers are captured to the log file. Safe mode **preserves** existing logs (does not wipe the crash session).

### Safe mode (after a crash)

If the UI won’t start but you need logs:

```text
python debug_server.py
python bike_train_transit.py --safe
```

Safe mode serves logs only — the dashboard shows crash marker, latest log, and previous session history. Run the full app again when ready.

### PC helpers (Windows)

```powershell
copy windows\bike-train-transit-windows.example.json windows\bike-train-transit-windows.json
# Edit phoneLanHost to your iPhone Wi-Fi IP

windows\BikeTrainTransit-Windows.ps1 -Action open
windows\BikeTrainTransit-Windows.ps1 -Action status
windows\BikeTrainTransit-Windows.ps1 -Action refresh
windows\BikeTrainTransit-Windows.ps1 -Action show-config
```

Log files on iPhone: `~/Documents/bike_train_transit/logs/`  
Log files on PC (when testing locally): `bike_train_transit/logs/`

---

## PC email script

Optional. Sends email via Yahoo SMTP when thresholds are hit (or every run if configured).

### Setup

```powershell
cd P:\all_scripts\bike_train_transit
copy .env.example .env
# Edit .env — Yahoo address + app password (not your normal login password)
```

Edit `config.json` for stations and thresholds.

### Run

```powershell
python bike_train_transit_alert.py --dry-run    # preview, no email
python bike_train_transit_alert.py              # send email

python bike_train_transit_alert.py --list-stations   # browse API station names
```

### Test Pythonista logic on PC

```powershell
python bike_train_transit.py --cli
```

Prints both **From JC** and **To JC** transit boards to the terminal.

---

## Configuration

### iPhone (`bike_train_transit.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `REGION` | `JC` | Tag shown on cards and in logs |
| `STATIONS` | JC names | GBFS station names or partial matches |
| `STATION_LABELS` | Short names | Compact UI labels (same order) |
| `GRID_GROUPS` | See file | 2-column card layout groups |
| `ALERT_MIN_BIKES` | `2` | Highlight when bikes ≤ this |
| `ALERT_MIN_DOCKS` | `2` | Highlight when empty docks ≤ this |
| `LAN_DEBUG_PORT` | `8765` | LAN debug server port |
| `TRANSIT_FETCH_TIMEOUT` | `12` | Seconds per transit API call |
| `BIKE_FETCH_TIMEOUT` | `12` | Seconds per GBFS call on refresh |

### Transit modules (`lib/`)

| File | Configure |
|------|-----------|
| `path_trains.py` | PATH stations for NYC, 33rd St, and NJ boards; PANYNJ `ridepath.json` fetched once per refresh |
| `subway_trains.py` | Subway north/Queens and To JC; `PATH_SUBWAY_WALK_MINUTES` for connection filtering |

### PC email (`config.json`)

| Field | Description |
|-------|-------------|
| `region` | Prefix tag for email reports (e.g. `JC`) |
| `stations` | List of station names (up to 12) |
| `alert_min_bikes` | Email alert threshold |
| `alert_min_docks` | Email alert threshold |
| `email_always` | `true` = email every run; `false` = only on alert |

### PC Windows helpers (`windows\bike-train-transit-windows.json`)

| Field | Description |
|-------|-------------|
| `phoneLanHost` | iPhone Wi‑Fi IP for LAN debug URLs |
| `lanDebugPort` | Debug server port (default `8765`) |
| `iCloudDownloads` | Optional override for `deploy.ps1` destination |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Stale code on iPhone after PC edits | Force quit Pythonista, delete old folder in Files, run `.\deploy.ps1`, reinstall from zip |
| App stuck in safe mode | Run `bike_train_transit.py` (full UI), not `debug_server.py` or `--safe` |
| Safe mode shows empty log | Update to latest code — safe mode now preserves crash logs; check **Previous session** on dashboard |
| Console errors not in LAN log | Update to latest code — stdout/stderr and thread errors are now captured |
| UI stuck on “Updating…” / black screen | Transit fetch may be slow; bikes should appear first. Check log for errors; redeploy latest code |
| App crashes on 2nd+ Refresh | Update to latest code (UI queue + `lib/parallel.py` closure fix). Run from **On This iPhone → Documents/bike_train_transit**, not iCloud Downloads |
| `fetch_json retry … JSON decoder returned tuple` | Harmless on older builds; latest code coerces Pythonista tuple JSON automatically |
| Shortcut tap does nothing / Pythonista doesn’t open | Use **Pythonista wrench → Shortcuts → Add to Home Screen** (not Shortcuts app). Test URL in **Safari** first. |
| Shortcut: “unable to locate file” | Run app once to install launcher; URL must be `pythonista3://RunBikeTrainTransit.py?action=run` |
| Shortcuts: “problem communicating with app” | Normal for UI apps — use Pythonista wrench method; launcher defers UI for URL handoff |
| Wrong IP in log (`10.115.x.x`) | That’s a VPN tunnel IP; use Wi‑Fi IP from Settings for PC access |
| `ModuleNotFoundError: lib` | Copy the whole folder including `lib/` |
| PC can’t reach debug URL | Same Wi‑Fi; check iPhone IP; app must be running (or safe mode after crash) |
| Email fails | Use Yahoo **app password** in `.env`, not account password |
| `deploy.ps1`: iCloud folder not found | Enable iCloud Drive on Windows or set `iCloudDownloads` in windows config |
| WTC subway shows `~` prefix | Estimated from Canal St +2 min — direct WTC E-line data was unavailable |

---

## API

Live bike data from:

- `https://gbfs.citibikenyc.com/gbfs/en/station_information.json`
- `https://gbfs.citibikenyc.com/gbfs/en/station_status.json`

**Filled** = `num_bikes_available`  
**Empty** = `num_docks_available` (open docks)

Transit data sources:

| Module | API |
|--------|-----|
| `lib/path_trains.py` | PANYNJ [ridepath.json](https://www.panynj.gov/bin/portauthority/ridepath.json) (primary, one fetch); [path.api.razza.dev](https://path.api.razza.dev/) fallback if PANYNJ fails |
| `lib/subway_trains.py` | [subwayinfo.nyc](https://subwayinfo.nyc/) arrivals API |
