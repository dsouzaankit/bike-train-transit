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

Bike cards appear first; transit sections load afterward. Network runs via Pythonista's `@ui.in_background` (not a raw thread). On the PC transit fetches in parallel; on Pythonista it fetches one at a time, since raw-thread or concurrent TLS can hard-crash the app.

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
    parallel.py                   # Parallel on PC, sequential on Pythonista (avoids TLS-thread crash)
    app_state.py                  # Shared state for UI / LAN status.json
    shortcut_launcher.py          # Deploys app to Documents; Home Screen uses the direct UI-script URL
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
- Copy itself to **On This iPhone → Documents/bike_train_transit/** (for the Home Screen URL)
- Install **`RunBikeTrainTransit.py`** on On This iPhone (legacy stub — not used for the Home Screen; see [iOS Home Screen](#ios-home-screen-one-tap-launch))
- Log shortcut setup steps to the console and LAN log

Launcher deploy runs in the background so the UI opens immediately. Only changed files are copied on redeploy.

### Updating after a code change (important)

The Home Screen shortcut runs the **`~/Documents/bike_train_transit/`** copy, **not** the iCloud/Downloads copy. iCloud sync only updates the Downloads copy — it does **not** refresh the Documents copy automatically.

After any code update (PC `deploy.ps1` or direct iCloud edit):

1. Open and **run `bike_train_transit.py` from the iCloud/Downloads copy once** in Pythonista.
2. That run re-deploys the changed files into Documents and rewrites the launcher.
3. The Home Screen shortcut now runs the updated code.

If you only tap the shortcut, it keeps running the old Documents copy.

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

Point the Home Screen icon at the **UI script** (`bike_train_transit.py`) directly, so it runs as the **main** script — exactly like pressing Run.

> **Do not use the `RunBikeTrainTransit.py` launcher stub for the Home Screen.** It runs the app nested via `runpy`, which breaks Pythonista’s UI run loop: `@ui.in_background` never fires and refresh hangs (you have to force-quit). A `ui.present` app must be the main script. (The `runpy` stub works for the SOCKS proxy only because that app is asyncio, not `ui`.)

### The URL

```
pythonista3://bike_train_transit/bike_train_transit.py?action=run
```

This targets the deployed copy at **On This iPhone → Documents/bike_train_transit/**. Run `bike_train_transit.py` once first so that copy exists. To get the URL from Pythonista: open that copy → **wrench** → **Pythonista URL** (older builds: **Add to Home Screen**).

### Make the Home Screen icon (Shortcuts app — two actions)

A single **Open URLs** action with the URL typed inline often does nothing for `pythonista3://` links. Use **two** actions so it is treated as a real URL:

1. **Shortcuts** → **+**
2. Add action **URL** → paste the URL above
3. Add action **Open URLs** (it takes the URL from step 2)
4. Settings (ⓘ) → turn **off** “Show in Share Sheet”
5. **⋯** → **Add to Home Screen**

Tapping the icon launches the app as the main script and refresh works. The first launch may prompt **“Open in Pythonista?” → Allow**.

### Test the URL first (Safari)

Paste the URL in **Safari’s address bar**. If the app opens and refreshes, the two-action Shortcut will too. (Pasting in Safari works even when a single-action “Open URLs” shortcut does nothing — that’s why the **URL → Open URLs** two-action recipe is required.)

### Alternative: run the iCloud copy directly

```
pythonista3://iCloud/Downloads/bike_train_transit/bike_train_transit.py?action=run&root=icloud
```

Use this only for the iCloud/Downloads copy; the Documents URL above is preferred for the Home Screen.

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
| App drops to safe mode during Refresh | Native crash from background-thread TLS. Update to latest code — refresh runs via `@ui.in_background` (Pythonista-managed) and `lib/parallel.py` fetches sequentially on Pythonista, so TLS never runs on a raw thread or concurrently |
| Shortcut tap does nothing / Pythonista doesn’t open | In Shortcuts use the **two-action** recipe: **URL** action + **Open URLs** action (a single inline “Open URLs” often fails for `pythonista3://`). Test the URL in **Safari** first. |
| Shortcut launches but refresh hangs / app freezes | The icon points at the `RunBikeTrainTransit.py` `runpy` stub, which breaks the UI loop. Point it at `pythonista3://bike_train_transit/bike_train_transit.py?action=run` instead (run as main script). |
| Shortcut: “unable to locate file” | Run `bike_train_transit.py` once so it deploys to Documents; URL must be `pythonista3://bike_train_transit/bike_train_transit.py?action=run` |
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
