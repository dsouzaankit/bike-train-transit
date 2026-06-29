# JC <-> NYC Transit

Monitor Citibike dock counts, PATH trains, NYC subway departures, and Lincoln/Holland tunnel travel times for Jersey City (`JC`). The iPhone UI header shows **JC <-> NYC Transit** — tabs: **Cbike JC**, **From JC**, **To JC**, **HBLR↔PATH**, and **Tunnels**. Includes a Pythonista app, optional PC email alerts, and a LAN debug server for reading logs from your desktop.

Uses the public [Citibike GBFS API](https://gbfs.citibikenyc.com/gbfs/en/) — no Citibike account login required.

## Features

- **Five tabs** — **Cbike JC**, **From JC**, **To JC**, **HBLR↔PATH**, and **Tunnels**
- **iPhone app** — compact 2-column Citibike grid on the **Cbike JC** tab (filled bikes and empty docks for JC stations)
- **Subway line badges** — MTA official line colors; cards show **one ETA per line** when data is available (taller cards fit all lines)
- **PATH + subway connections** — From JC **33rd St** subway cards only show trains reachable after the earliest paired PATH arrival + walk time; **HBLR↔PATH** has **PATH + Subway via WTC** under **HBLR → PATH** (**WTC Cortlandt** / **WTC** northbound, catchable after **LSP HBLR +11** then **Exchange PATH +8** walk at WTC)
- **HBLR ↔ PATH tab** — timed transfers; **Transit App API** is used only on this tab (see [Transit App API usage](#transit-app-api-usage))
- **PATH schedules** — trains terminating at **Hoboken** are excluded, but **"via Hoboken"** routings (the overnight 33rd↔JSQ service) are kept; **World Trade Center** additionally shows Hoboken-bound trains (HBLR transfer)
- **PATH & subway** — real-time departures in grouped sections (see [App tabs](#app-tabs) below); PATH uses one PANYNJ fetch for all boards
- **Compact ETAs** — `5m`, `Due`, `Delay` / `~5m`; southbound **6** (Union Sq) and **4/5** (Bleecker St express local) trains show **↓** (e.g. `14m↓`); card notes and destinations **wrap** within narrow columns (taller cards when needed)
- **Sorted departures** — train rows on each card sorted by ascending ETA
- **Low-count alerts** — cards highlight red when bikes or docks ≤ threshold
- **LAN debug server** — browse logs and status from a PC on the same Wi‑Fi (`:8765`)
- **PC deploy script** — `deploy.ps1` zips the project to iCloud Downloads for Pythonista sync
- **PC email script** — optional Yahoo SMTP status/alert emails
- **iOS Shortcut** — one-tap launch from Home Screen
- **Fullscreen UI** — Pythonista script title bar hidden; chrome starts ~1.5 cm below the top (`TOP_CONTENT_INSET`) so the title/tabs clear the iOS status bar (notch). Auto-refresh runs on launch (deferred just after `present()`)

## Jersey City stations (`JC`)

| | | |
|---|---|---|
| Dixon Mills | Montgomery St | Brunswick & 6th |
| Monmouth & 6th | Jersey & 6th St | Newport PATH |
| Washington St | City Hall | Grove St PATH |
| Liberty Light Rail | Exchange Pl | |
| JC Medical Center | | |

All stations are tagged `[JC]` in logs, email, and the **Cbike JC** tab.

## App tabs

Tap **Cbike JC**, **From JC**, **To JC**, **HBLR↔PATH**, or **Tunnels** in the tab bar. One refresh loads all tabs; switching tabs uses cached data (no extra network calls).

### Cbike JC

| Section | Stations | Data |
|---------|----------|------|
| **Citibike grid** | 12 JC stations | GBFS bike/dock counts |

Bike cards paint first after refresh; transit loads in the background for the other tabs. **Liberty Light Rail** and **Exchange Pl** share a row above **JC Medical Center** (own row at the bottom); long titles use two lines (`Liberty` / `Light Rail`, `JC` / `Medical Center`).

### From JC

| Section | Stations | Data |
|---------|----------|------|
| **PATH → NYC** | Grove St PATH, Newport PATH | Next NYC-bound PATH trains (Hoboken-terminating excluded; via-Hoboken kept) |
| **PATH + Subway · 33rd St** | Grouped tiles (see table below) | 33rd PATH + northbound subway, paired by corridor |

**PATH 14 St:** direct 33rd-bound arrivals at **14 St PATH** when available; otherwise estimated from **9th St** departure **+1 min** (`~`, note on card).

**Subway filter (33rd St):** only trains with `subway ETA ≥ paired PATH ETA + walk` are shown (earliest PATH arrival at the paired station). ETAs are **minutes from now** from the subway API — not adjusted. Card note: `after PATH 9th +5 walk`.

| Group | PATH | Subway | Walk |
|-------|------|--------|------|
| 1 | Christopher St | Christopher St | 5 min |
| 2 | 9th St | West 4 St | 5 min |

**West 4 St** subway card uses full headsign text (no `…` chop) with wrapped destination lines.
| 3 | 14 St PATH | 6 Av (L East/Bk), 14 St - Union Sq | 2 / 6 min |
| 4 | — | 51 St (4/5 ↑), 50 St (A express local) | — |
| 5 | — | Bleecker St (4/5 express local) | — |

**51 St**, **50 St**, and **Bleecker St** only list **express** trains when they make a **local stop** (4/5 at 51 St and Bleecker; A at 50 St). When express is skipping, the card says **Express not stopping** and notes which local lines are running (e.g. `Express skip · local 6` or `Express skip · local C/E`). When express is stopping, the note is **Express local stop**.

Layout on **From JC**: **PATH → NYC**, then **PATH + Subway · 33rd St** tile groups (two columns per row).

Transit-only tab (no bike grid) to keep scrolling short. **To JC** subway cards show **up to 2 ETAs per line** when available.

### To JC

| Section | Stations | Data |
|---------|----------|------|
| **Subway + PATH . Nwk** | WTC Cortlandt, World Trade Center (subway + PATH) | Downtown 1 / E toward South Ferry / WTC; NJ-bound PATH at WTC (incl. Hoboken) |
| **PATH → NJ** | Christopher St, 9th St, 33rd St | Next NJ-bound PATH trains |

**World Trade Center subway:** uses direct E-line arrivals when available. If not, estimates from **Canal St** WTC-bound departures **+2 min** (shown with `~` and note “est. Canal St + 2 min”). Cards show **up to 2 ETAs per line** when multiple lines serve the station. The **PATH WTC** card (tag `NJ`) sits in this section next to the subway tiles, and includes **Hoboken-bound** PATH trains.

### JC HBLR ↔ PATH

Four connection sections (primary departures + catchable secondary after the offset):

| Section | Primary | Secondary (after offset) | Offset |
|---------|---------|--------------------------|--------|
| **HBLR → PATH** | Liberty State Park HBLR (once, full width) | Exchange Place → WTC · Newport → 33rd (side by side) | 11 / 21 min |
| **PATH WTC → HBLR** | World Trade Center PATH (NJ-bound) | Exchange Place HBLR → Liberty State Pk | 7 min |
| **PATH 33rd St → HBLR** | Christopher St PATH (NJ-bound) | Newport HBLR → Liberty State Pk | 13 min |

**HBLR → PATH:** Exchange and Newport PATH cards show departures **catchable after LSP + offset** (11 / 21 min). PANYNJ first, then **Transit API** (filter pool **8**). Cards stay empty when nothing is reachable from LSP — no misleading raw PATH ETAs.

**PATH → HBLR:** secondary HBLR uses **Transit App → PDF** (NJT live middle step unavailable — see below). If nothing is catchable, live boards show **current HBLR** (`· current HBLR`).

**PATH + Subway via WTC:** subway timing chains from **LSP HBLR +11** to catchable Exchange PATH (WTC-bound), then **+8** walk at WTC. When PANYNJ or the subway API pool is too shallow, **Transit API** retries Exchange PATH and/or WTC subway stops (filter pool **8**); otherwise **current subway** (`· current subway`).

**HBLR data source (first match wins):** **[Transit App API](https://api-doc.transitapp.com/v4.html)** when `TRANSIT_API_KEY` or gitignored `transit_credentials.json` is set (real-time ETAs, 5 req/min free tier); otherwise **`lib/hblr_schedule_data.json`** — PDF timetable for **8th Street, West Side Ave, Liberty State Park, Exchange Place, and Newport**, both **north (Hoboken/Tonnelle)** and **south (Bayonne branches)** directions (marked `~`). Rebuild with `python tools/build_hblr_schedule.py` on PC when NJT updates the timetable.

**NJT Bus/Light-Rail API (middle step):** the app still supports `njt_credentials.json` / `NJTRANSIT_*` env vars (`pcsdata.njtransit.com`, `mode=HBLR`) as a fallback between Transit and PDF, but **NJ Transit developer API access is currently unavailable** — new registrations and dev tokens for this feed are not being issued, so in practice HBLR live data is **Transit App → PDF** only. The NJT code path remains for if/when access is restored.

**PDF parsing (`tools/build_hblr_schedule.py`):** extracts **departure times per station column**, not destination labels. The NJT PDF is a grid: left columns = north, right = south; each station has a fixed **x** position; times are read top-to-bottom in **AM** and **PM** bands. Tokens are 12-hour without AM/PM — each band repeats **12xx (noon)** → **1xx–11xx (afternoon/evening, +12 h)** → **12xx (midnight reset)** → **1xx–2xx (early AM through 02:45)**. `hblr_schedule_data.json` stores **`weekday` / `weekend`** as minutes from midnight (runtime) plus parallel **`weekday_pdf` / `weekend_pdf`** strings matching PDF tokens (debug).

**Transit vs PDF regression:** `python tools/capture_transit_hblr_fixtures.py` saves the three upstream Transit API responses under `tests/fixtures/transit_hblr/`. `test_hblr_transit_pdf_sync.py` checks each snapshot against the PDF parser at the same `captured_at` — failing tests mean rebuild the PDF (`build_hblr_schedule.py`) or tune `hblr_schedule.py`. Weekday **9:30 AM–3:30 PM** captures only validate API fixture shape (PDF omits those times); **evening/weekend** re-captures run strict board matching.

**Weekday gaps in the PDF:** many weekday columns omit midday times between AM and PM bands. The timetable footnote says trips continue every **10–20 minutes** on each route — those ranges are **intentionally not listed** in the PDF. Offline boards **fill those holes** using the active daypart headway from `_SCHED_WEEKDAY` (e.g. 10 min between 9:30 AM–3:30 PM), and still extend headway **after the last explicit time** in each pool.

**Offline line assignment (PDF fallback only):** the parser does **not** know Hoboken vs Tonnelle or 8th St vs West Side per timestamp. At runtime, `lib/hblr_schedule.py` assigns destinations heuristically — **northbound** labels each PDF list index per station (**Liberty State Park** and **Exchange Place** use the default Hoboken/Tonnelle cycle with a one-index phase offset at Exchange; **Newport** uses the Tonnelle-first cycle); **southbound** at Newport, Exchange Place, and Liberty State Park labels each station’s PDF `south_to_bayonne` times by **service-day order** (times sorted in the noon→02:45 window, then alternated 8th St / West Side Av). **Liberty State Park after midnight through 02:45** uses PDF list index+1 for overnight branch labels. **After 10 PM**, boards list explicit PDF departures first, then extend with 20-minute branch grids (deduped). **`minutes_until_departure()`** maps “minutes until” on the service-night timeline so afternoon PDF times are not shown as upcoming at midnight. Terminal stations (**8th Street**, **West Side Ave**) still use branch-terminal pools. Live NJT API returns the real destination per train.

**Weekend southbound (PDF fallback):** 20-minute headway from **noon–02:45**. At **Newport**, **Exchange Place**, and **Liberty State Park**, each branch keeps a 20-minute grid built from that station’s PDF column using the same service-day labeling. At **8th Street** and **West Side Ave** terminals, boards still use branch-terminal pools. Pairs are typically **5 min** apart (West Side after 8th St). **HBLR↔PATH** transfer boards use a larger raw pool (`raw_pool=36`) so post-midnight PDF times stay available for late-evening PATH connections. Live PATH boards are unchanged; weekend **PATH↔HBLR timing assumptions** use terminal-derived models in unit tests only (see [Unit tests](#unit-tests)).

#### Transit App API usage

Requires `TRANSIT_API_KEY` or gitignored `transit_credentials.json`. Other tabs (**Cbike JC**, **From JC**, **To JC**, **Tunnels**) do **not** call the Transit App API.

| Tab / section | Card | Role |
|---------------|------|------|
| **HBLR → PATH** | **Liberty State Park** HBLR | **Primary** live source (Transit App → PDF) |
| **HBLR → PATH** | **Exchange Place** PATH · **Newport PATH** | **Transfer retry** only — PANYNJ first; if offset filter finds nothing in the shallow pool, fetch up to **8** departures from Transit (`PATH:554` Exchange, `PATH:520` Newport), then filter **LSP +11 / +21**. Empty if still nothing catchable (no `· current PATH`) |
| **PATH + Subway via WTC** | Exchange PATH timing (hidden) | **Transfer retry** — LSP **+11** chain, then Transit `PATH:554` if needed |
| **PATH + Subway via WTC** | **WTC Cortlandt** ↑ · **WTC** ↑ | **Transfer retry** — subway API first; Transit `MTAS:19443` / `MTAS:19012` if pool too shallow for **Exchange +8** filter (pool **8**). May show `· current subway` when PATH is catchable but subway pool is thin |
| **PATH WTC → HBLR** | **Exchange Place** HBLR | **Primary** live source (Transit `NJTR:3076` → PDF). **No** extra Transit retry on the transfer filter |
| **PATH 33rd St → HBLR** | **Newport** HBLR | **Primary** live source (Transit `NJTR:3079` → PDF). **No** extra Transit retry on the transfer filter |

**HBLR tiles and PDF:** only the three **HBLR** cards above use `get_hblr_board()` (Transit App → PDF in practice; NJT API code remains but dev tokens are **currently unavailable**). All three can fall back to **`hblr_schedule_data.json`** (`~` / `sched`) when live feeds fail. **PATH** and **subway** cards on this tab use PANYNJ / subway APIs — not the HBLR PDF. **8th Street** and **West Side Ave** exist in the PDF data for offline logic but are **not** shown as UI cards.

**PATH → HBLR** live HBLR secondaries may show **`· current HBLR`** when nothing meets the offset; PDF (`~`) HBLR boards stay empty when nothing is catchable.

### Tunnels

| Section | Data source | Data |
|---------|-------------|------|
| **Lincoln & Holland** | [PANYNJ crossing times](https://www.panynj.gov/bin/portauthority/crossingtimesapi.json) (same backend as [Bridges & Tunnels](https://www.panynj.gov/bridges-tunnels/en/index.html)) | Full-width cards in fixed order — **Lincoln Tunnel** then **Holland Tunnel**, each with **→ NYC** above **→ NJ** travel minutes and green / amber / red pills matching the website |

## Project layout

```
bike_train_transit/
  bike_train_transit.py           # iPhone UI (Pythonista)
  bike_train_transit_alert.py     # PC email script
  deploy.ps1                      # Zip + copy to iCloud Downloads (PC → iPhone)
  config.json                     # PC stations + thresholds
  debug_server.py                 # Safe mode: logs only (no UI)
  lib/
    path_trains.py                # PATH NYC / 33rd / NJ (PANYNJ single-fetch; Hoboken-terminating filtered, via-Hoboken kept, WTC allows Hoboken)
    hblr_path.py                  # HBLR↔PATH tab: four transfer pairs + offset filter
    hblr_schedule.py              # Load pre-parsed HBLR PDF timetable (hblr_schedule_data.json)
    hblr_schedule_data.json       # HBLR PDF times: 5 stations × 2 directions (built on PC)
    path_schedule.py              # Test-only weekend PATH phase model (not used by live UI)
    transit_app.py                # Transit App API v4 stop departures (primary HBLR live source)
    light_rail.py                 # HBLR station fetch (Transit App → NJT* → PDF fallback)
    subway_trains.py              # Subway north and To JC boards
    subway_lines.py               # MTA line badge colors
    tunnel_crossings.py           # Lincoln/Holland PANYNJ crossingtimesapi.json
    parallel.py                   # Parallel on PC, sequential on Pythonista (avoids TLS-thread crash)
    app_state.py                  # Shared state for UI / LAN status.json
    shortcut_launcher.py          # Deploys app to Documents; reports direct UI-script URL; removes obsolete stub
    local_deploy.py               # Incremental copy to On This iPhone (incl. transit_credentials.json)
    credential_paths.py           # Resolve API credential JSON on PC and Pythonista Documents
    file_logging.py, log_paths.py # Session logs + safe-mode preservation
    lan_debug_server.py           # LAN debug HTTP server
  tests/                          # Unit tests (HBLR, PATH transfers, weekend sync, From JC express-local)
  tools/
    build_hblr_schedule.py        # PC-only: parse NJT HBLR PDF → hblr_schedule_data.json (pymupdf; 12-hour band cycles)
    capture_transit_hblr_fixtures.py  # PC-only: snapshot 3 Transit API boards → tests/fixtures/transit_hblr/
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
cd "P:\all_scripts\iOS apps\bike_train_transit"
.\deploy.ps1
```

The script:

1. Removes old `bike_train_transit.zip` and `bike_train_transit\` from iCloud Downloads
2. Stages the project (excludes logs, `windows/`, `ai/`, PC-only email files, editor junk). If present locally, **`transit_credentials.json`** and **`njt_credentials.json`** are included in the zip.
3. Creates `bike_train_transit.zip` and copies it to `%USERPROFILE%\iCloudDrive\Downloads`

Optional: set `iCloudDownloads` in `windows\bike-train-transit-windows.json` if your iCloud path differs.

### 4. Install on iPhone

1. **Files → iCloud Drive → Downloads**
2. Tap **`bike_train_transit.zip`** to unzip
3. Copy the **`bike_train_transit`** folder into Pythonista
4. Run **`bike_train_transit.py`** once

On first launch the app will:

- Show the **From JC** tab (default) and refresh live data; bikes appear on **Cbike JC**
- Start the LAN debug server on port **8765**
- Copy itself to **On This iPhone → Documents/bike_train_transit/** (for the Home Screen URL), including **`transit_credentials.json`** / **`njt_credentials.json`** when they sit next to the main script
- Remove the obsolete **`RunBikeTrainTransit.py`** stub if present (its `runpy` launch breaks the UI loop; the Home Screen uses the direct UI-script URL instead — see [iOS Home Screen](#ios-home-screen-one-tap-launch))
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

### Double back-tap launch (iOS)

Use iOS **Back Tap** to run the same Shortcut without opening Shortcuts manually:

1. Build the **URL → Open URLs** Shortcut above (name it e.g. `Bike Train Transit`).
2. **Settings → Accessibility → Touch → Back Tap → Double Tap**
3. Choose **Shortcut** → select **Bike Train Transit**

Double-tapping the back of the iPhone runs the Shortcut and opens Pythonista at the deployed `bike_train_transit.py` URL. This uses the same direct UI-script URL as the Home Screen icon.

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
| `/bike_train_transit_latest.txt` | Full session log (`build=hblr-path-v16`; HBLR boards log `[transit]` / `[pdf]` source) |
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
cd "P:\all_scripts\iOS apps\bike_train_transit"
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

### Unit tests

```powershell
cd "P:\all_scripts\iOS apps\bike_train_transit"
python -m unittest discover -s tests -q
```

Covers HBLR PDF parsing (`test_build_hblr_schedule.py`), **Transit API vs PDF sync** (`test_hblr_transit_pdf_sync.py` + `tools/capture_transit_hblr_fixtures.py` — committed snapshots, not live API on every run), Transit App departure parsing (`test_transit_app.py`), **Pythonista credential deploy** (`test_credential_paths.py`), **weekday PDF gap headway fill** (`test_hblr_schedule.py`), **Exchange PATH → WTC subway connection** (`test_exchange_wtc_subway.py`), **evening and overnight PDF vs Google Maps reference** departures for all five stations (`test_hblr_pdf_evening_reference.py`, Sun ~8:25 PM and late-night weekday wraps), weekend southbound branch headways, HBLR↔PATH transfer offsets including post-midnight pooling (`test_light_rail_offset.py`, `test_hblr_path_sections.py`), From JC **express-local** subway cards (`test_subway_from_jc_stations.py` — **51 St**, **50 St**, **Bleecker St**), and weekend **PATH↔HBLR sync models** (`test_weekend_hblr_path_sync.py`):

| Model (tests only) | Assumption |
|--------------------|------------|
| West Side Av @ Newport / Exchange | Departs **5 min** after 8th St toward Liberty State Park |
| PATH 33rd @ Newport | Every **10 min** (12p–9p); every other arrival aligns with **20 min** West Side HBLR |
| PATH Newark-line WTC @ Exchange | Every **20 min** (12p–11p); matches **8th St** HBLR (not Hoboken-line WTC) |

Live PATH fetching in `lib/path_trains.py` does not filter by PATH line color; Newark vs Hoboken distinction is documented and checked only in tests.

---

## Configuration

### iPhone (`bike_train_transit.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `APP_TITLE` | `JC <-> NYC Transit` | Header title and view name in the UI |
| `TOP_CONTENT_INSET` | `43` | Points (~1.5 cm) from screen top to title row — clears iOS status bar / notch (title bar is hidden) |
| `REGION` | `JC` | Tag shown on bike cards and in logs |
| `STATIONS` | JC names | GBFS station names or partial matches |
| `STATION_LABELS` | Short names | Compact UI labels (same order); use `\n` for a two-line card title |
| `GRID_GROUPS` | See file | 2-column card layout groups; `None` = empty spacer cell |
| `ALERT_MIN_BIKES` | `2` | Highlight when bikes ≤ this |
| `ALERT_MIN_DOCKS` | `2` | Highlight when empty docks ≤ this |
| `LAN_DEBUG_PORT` | `8765` | LAN debug server port |
| `TRANSIT_FETCH_TIMEOUT` | `12` | Seconds per transit API call |

### Transit modules (`lib/`)

| File | Configure |
|------|-----------|
| `path_trains.py` | PATH stations; PANYNJ `ridepath.json`; `get_path_transit_board()` for HBLR-tab PATH transfer retry (`PATH:554` Exchange, `PATH:520` Newport, `PATH:553` WTC, `PATH:552` Chris St) |
| `light_rail.py` | HBLR station boards by direction; Transit API key (`transit_credentials.json` / `TRANSIT_API_KEY`); optional NJT creds (`njt_credentials.json`) — **NJT dev API currently unavailable**; PDF fallback via `hblr_schedule_data.json` |
| `transit_app.py` | Transit App v4 `/stop_departures` client; per-stop cache (~45s) to stay within 5 req/min |
| `hblr_path.py` | HBLR↔PATH sections; `path_catchable_after_lsp()` (LSP → PATH + Transit retry); `resolve_transfer_board()` for PATH→HBLR and WTC subway (`· current HBLR` / `· current subway` fallbacks where applicable) |
| `hblr_schedule.py` | Loads `hblr_schedule_data.json` for offline HBLR departures; **weekday daytime** fills PDF midday holes with service headway; PDF times have no per-line label — **northbound** PDF list index per station (LSP/Exchange default Hoboken/Tonnelle cycle; Exchange phase +1; Newport Tonnelle-first); **southbound** upstream stations label PDF columns by service-day order (`_south_labeled_explicit`; LSP index+1 only after midnight–02:45); `minutes_until_departure()` for service-night ETAs; terminals use branch-terminal pools; weekend south through **02:45** |
| `path_schedule.py` | Weekend PATH phase helpers for unit tests only (not wired to live UI) |
| `subway_trains.py` | Subway north/Queens and To JC; `SUBWAY_PATH_WALKS` for **33rd St** connection filtering; **PATH + Subway via WTC** on HBLR tab (`get_wtc_north_boards`, `get_subway_transit_board` at `MTAS:19443` / `MTAS:19012`, **LSP HBLR +11** then **Exchange +8**); **51 St** / **50 St** / **Bleecker St** express-local cards; southbound **6** (Union Sq) and **4/5** (Bleecker express local) ETAs append **↓** |

Copy `transit_credentials.json.example` → `transit_credentials.json` (gitignored) with your [Transit App API](https://transitapp.com/apis) key. `deploy.ps1` includes this file when present so the iPhone gets live HBLR ETAs.

**Pythonista:** the Home Screen shortcut runs from `On My iPhone → Documents → bike_train_transit/`, not the folder you edit in the Pythonista file browser. Put `transit_credentials.json` next to `bike_train_transit.py` in your edit folder, then **run the script once** so `local_deploy` copies it to Documents. You can also create the file directly under `Documents/bike_train_transit/`. Live HBLR cards show **no `~` prefix**; `~` means PDF fallback.

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
| Open shows empty data until Refresh tapped | Run as **main script** (Home Screen direct URL, not `RunBikeTrainTransit.py`). Update to latest code — startup refresh is deferred via `ui.delay` **after** `present()` so the UI run loop is active (log shows `kickoff: poll + first refresh`) |
| Title overlaps the iOS status bar / notch | Increase `TOP_CONTENT_INSET` in `bike_train_transit.py` (default `43` ≈ 1.5 cm) |
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
| PATH missing Hoboken | Hoboken-terminating trains are filtered out; "via Hoboken" routings are kept, and World Trade Center shows Hoboken-bound trains |
| HBLR shows `~`/`sched` | PDF timetable fallback — Transit App key missing or fetch failed. On Pythonista, confirm `transit_credentials.json` is in **Documents/bike_train_transit/** (run `bike_train_transit.py` once after adding it to your edit folder). Card note may say `sched · …` if the API key was found but the fetch failed |
| NJT `njt_credentials.json` does nothing | Expected for now — **NJ Transit developer API tokens for HBLR are currently unavailable**; live HBLR is Transit App only, then PDF. Code path kept for if access returns |
| HBLR empty / “None catchable” | No train meets the offset from the primary. **HBLR → PATH** PATH cards stay empty (note `LSP HBLR +11` / `+21`). **PATH → HBLR** may show `· current HBLR`; **WTC subway** may show `· current subway`. PDF (`~`) HBLR boards stay empty when nothing is catchable |
| Subway card is taller | One row per line (earliest ETA per line); normal when many lines serve the station |

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
| `lib/transit_app.py` | [Transit App API v4](https://api-doc.transitapp.com/v4.html) `/stop_departures` — **HBLR↔PATH tab only** (see [Transit App API usage](#transit-app-api-usage)); per-stop cache ~45s |
| `lib/path_trains.py` | PANYNJ [ridepath.json](https://www.panynj.gov/bin/portauthority/ridepath.json) (primary, one fetch); [path.api.razza.dev](https://path.api.razza.dev/) fallback if PANYNJ fails |
| `lib/light_rail.py` | Transit App (primary HBLR live) → NJT Bus/Light-Rail API (supported in code; **dev tokens currently unavailable**) → `hblr_schedule_data.json` PDF |
| `lib/subway_trains.py` | [subwayinfo.nyc](https://subwayinfo.nyc/) arrivals API |
| `lib/tunnel_crossings.py` | PANYNJ [crossingtimesapi.json](https://www.panynj.gov/bin/portauthority/crossingtimesapi.json) |
