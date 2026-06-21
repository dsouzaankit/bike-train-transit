# Bike Train Transit

Monitor Citibike dock counts, PATH trains, and NYC subway departures for Jersey City (`JC`) stations — plus a **To JC** tab for downtown subway and NJ-bound PATH from Manhattan. Includes an iPhone UI (Pythonista), optional PC email alerts, and a LAN debug server for reading logs from your desktop.

Uses the public [Citibike GBFS API](https://gbfs.citibikenyc.com/gbfs/en/) — no Citibike account login required.

## Features

- **Two tabs** — **From JC** (bikes + outbound transit) and **To JC** (inbound transit from Manhattan)
- **iPhone app** — compact 2-column grid showing filled bikes and empty docks for JC stations
- **PATH + subway connections** — From JC subway cards filter for trains reachable after PATH arrival + walk time
- **PATH & subway** — real-time departures in grouped sections (see [App tabs](#app-tabs) below)
- **Low-count alerts** — cards highlight red when bikes or docks ≤ threshold
- **LAN debug server** — browse logs and status from a PC on the same Wi‑Fi (`:8765`)
- **PC deploy script** — `deploy.ps1` zips the project to iCloud Downloads for Pythonista sync
- **PC email script** — optional Yahoo SMTP status/alert emails
- **iOS Shortcut** — one-tap launch from Home Screen (launcher v7 two-hop handoff)

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
| **Subway → North / Queens** | Christopher St, West 4 St | Uptown/Queens departures after PATH + walk |

On refresh, the **bike grid paints first**; PATH and subway sections follow once transit data is loaded. Transit data is fetched in parallel in the background.

**Subway → North / Queens** uses the earliest PATH arrival at **Christopher St** or **9th St** (from PATH → 33rd) and only shows subway departures you can catch after a walk:

| Subway station | Walk buffer after PATH |
|----------------|------------------------|
| Christopher St (1 train) | +5 min |
| West 4 St (A/C/E/B/D/F/M) | +7 min |

Each subway card shows a note like `after PATH +5 min`. Empty state: **None after PATH**.

### To JC

| Section | Stations | Data |
|---------|----------|------|
| **Subway → South Ferry** | WTC Cortlandt, World Trade Center | Downtown 1 train (South Ferry) and E train at WTC |
| **PATH → NJ** | Christopher St, 9th St, 33rd St, World Trade Center | Next NJ-bound PATH trains (2×2 grid) |

**World Trade Center (E train)** — card note tells you which source is in use:

| Card note | Meaning |
|-----------|---------|
| `E @ WTC (direct)` | Live E-line arrivals at the WTC platform (`E01`) |
| `E est. Canal St +2 min` | No direct WTC E data; estimated from Canal St WTC-bound trains +2 min (`~` on ETAs) |

WTC Cortlandt shows **1 train** arrivals toward South Ferry directly.

## Project layout

```
bike_train_transit/
  bike_train_transit.py           # iPhone UI (Pythonista)
  bike_train_transit_alert.py     # PC email script
  deploy.ps1                      # Zip + copy to iCloud Downloads (PC → iPhone)
  config.json                     # PC stations + thresholds
  debug_server.py                 # Safe mode: logs only (no UI)
  lib/
    path_trains.py                # PATH NYC / 33rd / NJ boards
    subway_trains.py              # Subway north, PATH+subway connections, To JC
    parallel.py                   # Pythonista-safe parallel fetch (no ThreadPoolExecutor)
    app_state.py                  # Shared state for UI, CLI, LAN status
    file_logging.py               # Log tee, crash hooks, session archive
    shortcut_launcher.py          # RunBikeTrainTransit.py launcher (v7)
    local_deploy.py               # Incremental copy to On This iPhone
    lan_debug_server.py           # HTTP debug server
    ...                           # app_control, log_paths, net_util
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
- **Pythonista → On This iPhone** — remove `bike_train_transit/` and stale launchers if present

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
3. Copy the **`bike_train_transit`** folder into Pythonista (iCloud Downloads is fine for **editing**)
4. Run **`bike_train_transit.py`** once from the copied folder

On first launch the app will:

- Show the **From JC** tab with bike grid and refresh live data
- Start the LAN debug server on port **8765**
- Copy itself to **On This iPhone → Documents/bike_train_transit/** (required for shortcuts and URL launch)
- Install **`RunBikeTrainTransit.py`** (launcher v7) on On This iPhone
- Log shortcut setup steps to the console and LAN log

Launcher deploy runs in the background so the UI opens immediately. Only changed files are copied on redeploy.

**Important:** Edit in iCloud Downloads if you like, but the **runnable copy** lives under **On This iPhone → Documents/bike_train_transit/** after the first run. Re-run `bike_train_transit.py` after each deploy to sync changes there.

---

## iPhone setup (manual alternatives)

If you are not using `deploy.ps1`:

- **iCloud** — sync via Files / iCloud Drive (e.g. `Downloads/bike_train_transit/`)
- **Copy/paste** — paste `bike_train_transit.py` + `lib/` into Pythonista

Always copy the **entire folder including `lib/`**, not just the main script.

### Edit stations (optional)

In `bike_train_transit.py`, edit `STATIONS`, `STATION_LABELS`, `GRID_GROUPS`, and `REGION` at the top. Transit station lists and walk buffers live in `lib/path_trains.py` and `lib/subway_trains.py`.

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

**Launcher v7** uses a two-hop handoff: the shortcut opens `RunBikeTrainTransit.py`, which immediately re-opens the full app via `shortcuts.open_url()`. This avoids the Shortcuts error `ui.View.present is not available in widgets and shortcuts`.

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

Console output (`stdout`/`stderr`), thread tracebacks, and crash markers are captured to the log file.

### Logging behavior

- Each **full app launch** archives the previous latest log to a timestamped history file before starting a new session
- **Crash marker** (`bike_train_transit_crash.txt`) is kept until a successful **Refresh OK**
- Refresh logs step markers: `Refresh started` → `Bikes fetched` → `Transit fetch started/done` → `Refresh OK`
- UI updates during refresh run on the **main thread** (background thread only fetches data)
- GBFS and transit HTTP fetches **retry** on transient failures

### Safe mode (after a crash)

If the UI won’t start but you need logs:

```text
python debug_server.py
python bike_train_transit.py --safe
```

**Force quit the full app first** — safe mode cannot bind port 8765 if Bike Train Transit is still running (`address already in use`).

Safe mode:

- Does **not** wipe existing logs
- Recovers latest log from **Previous session** history if latest is empty
- Serves crash marker, latest log, and session history on the dashboard

Run the full app again when ready.

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
| `path_trains.py` | PATH stations for NYC, 33rd St, and NJ boards |
| `subway_trains.py` | Subway north/Queens (PATH connection filters), To JC (WTC Cortlandt, WTC E, Canal St fallback) |
| `subway_trains.py` | `PATH_SUBWAY_WALK_MINUTES` — walk after PATH before subway (Christopher St: 5, West 4 St: 7) |
| `subway_trains.py` | `CANAL_WTC_ESTIMATE_MINUTES` — added to Canal St times when WTC E direct data unavailable (default: 2) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Stale code on iPhone after PC edits | Force quit Pythonista, delete old folder in Files + On This iPhone, run `.\deploy.ps1`, reinstall from zip, run `bike_train_transit.py` once |
| App stuck in safe mode | Run `bike_train_transit.py` (full UI), not `debug_server.py` or `--safe` |
| Safe mode: port 8765 already in use | Force quit the full Bike Train Transit app first, then start safe mode |
| Safe mode shows empty log | Check **Previous session** on dashboard; latest code auto-recovers from history |
| Console errors not in LAN log | stdout/stderr and thread errors are tee'd to the log |
| App crashes on Refresh or From JC tab | Redeploy latest code; UI is main-thread only with deferred transit paint. Check log for last step before crash |
| UI stuck on “Updating…” | Bikes should appear first; check log for `Transit fetch` / `UI finish failed` |
| Refresh fails: GBFS tuple/object error | Transient network glitch — retry Refresh; fetch retries automatically |
| Shortcut: `ui.View.present is not available` | Update to launcher v7 — run app once to reinstall `RunBikeTrainTransit.py` |
| Shortcut tap does nothing | Use **Pythonista wrench → Add to Home Screen** on `RunBikeTrainTransit.py`. Test URL in **Safari** first |
| Shortcut: “unable to locate file” | Run app once to install launcher; URL must be `pythonista3://RunBikeTrainTransit.py?action=run` |
| `lib/ shortcut help unavailable` | Harmless when editing in Downloads — launcher still installs to On This iPhone |
| Wrong IP in log (`10.115.x.x`) | VPN tunnel IP; use Wi‑Fi IP from Settings for PC access |
| `ModuleNotFoundError: lib` | Copy the whole folder including `lib/` |
| PC can’t reach debug URL | Same Wi‑Fi; check iPhone IP; app must be running (or safe mode after force quit) |
| Email fails | Use Yahoo **app password** in `.env`, not account password |
| `deploy.ps1`: iCloud folder not found | Enable iCloud Drive on Windows or set `iCloudDownloads` in windows config |
| WTC card note `E est. Canal St +2 min` | Fallback estimate — direct WTC E feed had no arrivals |
| WTC card note `E @ WTC (direct)` | Live E-line data at WTC platform |
| Subway shows “None after PATH” | No uptown subway departs soon enough after next PATH arrival + walk buffer |
| PATH → NJ cards overflow | Section uses 2×2 grid layout (update if still broken after redeploy) |

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
| `lib/path_trains.py` | PANYNJ `ridepath.json` (primary; one fetch for all boards). Optional razza.dev per-station fallback when PANYNJ is empty. |
| `lib/subway_trains.py` | [subwayinfo.nyc](https://subwayinfo.nyc/) arrivals API |

Parallel transit fetches use `lib/parallel.py` (threading-based) — Pythonista’s `ThreadPoolExecutor` is broken and must not be used.
