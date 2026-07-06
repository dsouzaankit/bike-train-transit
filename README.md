# JC <-> NYC Transit

Monitor Citibike dock counts, PATH trains, NYC subway departures, and Lincoln/Holland tunnel travel times for Jersey City (`JC`). The iPhone UI header shows **JC <-> NYC Transit** — tabs: **Cbike JC**, **From JC**, **To JC**, **HBLR↔PATH**, and **Tunnels**. Includes a Pythonista app, optional PC email alerts, and a LAN debug server for reading logs from your desktop.

Uses the public [Citibike GBFS API](https://gbfs.citibikenyc.com/gbfs/en/) — no Citibike account login required.

## Features

- **Five tabs** — **Cbike JC**, **From JC**, **To JC**, **HBLR↔PATH**, **Tunnels**, and **MT→JC**
- **iPhone app** — compact 2-column Citibike grid on the **Cbike JC** tab (filled bikes and empty docks for JC stations)
- **Subway line badges** — MTA official line colors; cards show **one ETA per line** when data is available (taller cards fit all lines)
- **PATH + subway connections** — From JC **33rd St** subway cards only show trains reachable after the earliest paired PATH arrival + walk time; **HBLR↔PATH** has **PATH + Subway via WTC** under **HBLR → PATH** (**WTC Cortlandt** / **WTC** northbound, catchable after **LSP HBLR +11** then **Exchange PATH +8** walk at WTC)
- **HBLR ↔ PATH tab** — timed transfers; **Transit App API** is used only on this tab (see [Transit App API usage](#transit-app-api-usage))
- **PATH schedules** — trains terminating at **Hoboken** are excluded, but **"via Hoboken"** routings (the overnight 33rd↔JSQ service) are kept; **World Trade Center** additionally shows **Hoboken-bound** PATH trains; for travel near **Liberty State Park**, **change at Exchange Place** (HBLR ↔ PATH) — see [HBLR↔PATH](#jc-hblr--path)
- **PATH & subway** — real-time departures in grouped sections (see [App tabs](#app-tabs) below); PATH uses one PANYNJ fetch for all boards
- **Compact ETAs** — `5m`, `Due`, `Delay` / `~5m`; southbound **6** (Union Sq) and **4/5** (Bleecker St express local) trains show **↓** (e.g. `14m↓`); card notes and destinations **wrap** within narrow columns (taller cards when needed)
- **Sorted departures** — train rows on each card sorted by ascending ETA
- **Low-count alerts** — cards highlight red when bikes or docks ≤ threshold
- **LAN debug server** — browse logs and status from a PC on the same Wi‑Fi (`:8765`)
- **PC deploy script** — `deploy.ps1` zips the project to iCloud Downloads for Pythonista sync
- **PC email script** — optional Yahoo SMTP status/alert emails
- **iOS Shortcut** — one-tap launch from Home Screen
- **Fullscreen UI** — Pythonista script title bar hidden; layout uses **safe area insets** on iPhone 12+ (notch / Dynamic Island / home indicator). Auto-refresh on launch (deferred just after `present()`); no manual Refresh button
- **Startup thumb float** — on open, section tabs stack **vertically** toward screen center for 5s; **hold Prolong** pauses the timer (red + haptic); tabs **gray out** until startup refresh finishes

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

Tap **Cbike JC**, **From JC**, **To JC**, **HBLR↔PATH**, **Tunnels**, or **MT→JC** in the tab bar. Data loads when you **tap a tab** (or LAN `/refresh` for the active tab only); switching tabs without a new tap uses in-memory cache. See [HTTP cache and refresh API calls](#http-cache-and-refresh-api-calls).

### MT→JC tab

Three rows (**50 St 8Av**, **50 St 7Av**, **Lex/53 St**). Each row is **5 cards in 3 columns**:

| Column | Cards |
|--------|--------|
| **Subway** | **50 St (8Av):** E · **50 St (7Av):** 1 · **Lex/53:** E/1/F (F **Mon–Fri 6a–9:30p** only) |
| **PATH stack** | NJ-bound **Newark / JSQ / Hoboken** from **9 St** or **Chris St** (+offset from subway) and **WTC** (+offset from subway); **all six PATH cards** use the same destination filter and **`allow_hoboken`** (terminating Hoboken kept; **via Hoboken** overnight routings excluded). **Transit App retry** (`PATH:551` 9 St, `PATH:552` Chris St, `PATH:553` WTC) when PANYNJ pool is shallow |
| **HBLR stack** | Southbound **Newport** (+offset from 9 St/Chris PATH) and **Exchange Place** (+offset from WTC PATH); **Transit retry**, empty if nothing catchable (no “current HBLR” platform times) |

**Offset chain** (subway → PATH → HBLR; PATH/HBLR use `resolve_transfer_board` + Transit retry, no `· current` fallback):

| Row | Subway | PATH (from subway) | HBLR (from PATH) |
|-----|--------|--------------------|------------------|
| **50 St (8Av)** | E (+ F wkdys) | 9 St +15m, WTC +**19**m | Newport +14m ← 9 St; Exchange +7m ← WTC |
| **50 St (7Av)** | 1 (+ F wkdys) | Chris St +15m, WTC +20m | Newport +13m ← Chris St; Exchange +7m ← WTC |
| **Lex/53 St** | E/1/F | 9 St +20m, WTC +25m | Newport +14m ← 9 St; Exchange +7m ← WTC |

Log markers: `build=hblr-path-v75`, `step: MT→JC rows (3)`.

### Startup thumb float (~6" screens)

On launch (after `present()`), section tabs **float** in a vertical column pulled toward the horizontal center (left-hand thumb on ~6" phones):

| Behavior | Detail |
|----------|--------|
| **Trigger** | App startup only (no auto-fetch until you tap a tab) |
| **Position** | Vertical stack on screen center line; stack center at 65% usable height |
| **Prolong** | Top of stack; **hold** pauses the 5s timer (pill turns **red** + haptic); **release** re-arms +5s |
| **Section tabs** | **MT→JC** nearest thumb at stack bottom; **grayed out** while that tab is fetching |
| **Section tab tap** | Highlights tapped pill, switches tab, **docks** tabs, and **fetches only that tab** |
| **5s idle** | Tabs dock to the top bar (timer starts when idle after a tab fetch, or immediately on launch) |

Log markers: `build=hblr-path-v75`, `kickoff: poll (tap tab to load)`, `Refresh tab mt_to_jc (#1)`, `thumb float armed 5s`.

## HTTP cache and refresh API calls

Data loads when you **tap a section tab** (thumb float or docked tab bar) and via **LAN debug** refresh (active tab only). There is no manual Refresh button and no startup auto-fetch.

### 2-minute persistent cache

All live HTTP JSON responses go through `lib/http_cache.py`:

| Setting | Value |
|---------|-------|
| **TTL** | **2 minutes** (`HTTP_CACHE_TTL_SEC = 120`) |
| **Storage** | `Documents/bike_train_transit/http_cache/` (survives app restarts until expiry) |
| **Scope** | Citibike GBFS, PANYNJ PATH + tunnels, `subwayinfo.nyc`, Transit App |
| **Bypass** | `BIKE_TRAIN_TRANSIT_NO_HTTP_CACHE=1` |
| **Logs** | `http cache hit: <url>` when a cached body is reused |

PANYNJ cache-bust query `?_=…` is stripped for the cache key (one PATH payload per 2 min). Subway and Transit URLs keep full query strings (station, direction, stop id, etc.).

A **second refresh within 2 minutes** (or relaunch within TTL) typically reuses most responses — often **0 network calls** if nothing expired. After TTL, that URL is fetched again and re-cached.

### HTTP calls per refresh (cache cold)

Counts are **network requests** on a full refresh when the 2-minute cache is empty. Shared fetches are counted once.

| API | Typical calls | Notes |
|-----|---------------|--------|
| **Citibike GBFS** | **2** | `station_information.json` + `station_status.json` |
| **PANYNJ PATH** | **1** | `ridepath.json` — all PATH cards (NYC, 33rd, NJ, HBLR PATH, Exchange WTC) |
| **PANYNJ tunnels** | **1** | `crossingtimesapi.json` |
| **subwayinfo.nyc** | **15–16** | See breakdown below |
| **Transit App** | **3** | HBLR live only — LSP, Exchange Place, Newport (`NJTR:…`); **0** if no API key (PDF fallback) |
| **Transit retries** | **0–4** | HBLR tab only — deeper PATH/subway pool when transfer filter is shallow |

**Typical cold refresh total: ~22–23 HTTP calls.**

#### subwayinfo.nyc breakdown

| Block | Calls |
|-------|------:|
| **From JC** — Chris St, West 4 (A+D), 6 Av, Union Sq (4 direction queries), 51 St, 50 St, Bleecker | **11** |
| **To JC** — WTC Cortlandt, WTC E (+ Canal St **+1** if E platform empty) | **1–2** |
| **HBLR WTC section** — WTC Cortlandt ↑, WTC ↑ (northbound; separate from To JC south) | **2** |

WTC/Cortlandt are fetched twice (south for **To JC**, north for **HBLR**) with different `direction` parameters.

#### Per-tab data (not separate fetches)

| Tab | Primary sources | Attributed calls* |
|-----|-----------------|------------------:|
| **Cbike JC** | GBFS | **2** |
| **From JC** | PANYNJ slice + From JC subway | **12** |
| **To JC** | PANYNJ NJ slice + To JC subway | **2–3** |
| **HBLR↔PATH** | Transit HBLR + PANYNJ PATH slice + WTC subway north + optional retries | **5–9** |
| **Tunnels** | PANYNJ crossing times | **1** |

\*PANYNJ PATH (**1**) and GBFS (**2**) are **shared** — do not sum the “Attributed” column for a total.

#### Debug entrypoints (fewer calls)

| Script / env | Skips |
|--------------|--------|
| `debug_citibike_inactive.py` | GBFS (−2) |
| `debug_path_inactive.py` | PANYNJ PATH (−1) |
| `debug_subway_inactive.py` | subwayinfo.nyc (−15–16) |
| `debug_hblr_inactive.py` | HBLR Transit (−3; PDF = 0 HTTP) |
| `BIKE_TRAIN_TRANSIT_INACTIVE=…` | Same flags, combinable |

Not called on refresh: **NJT HBLR API** (unavailable), **path.api.razza.dev** (disabled).

### Cbike JC

| Section | Stations | Data |
|---------|----------|------|
| **Citibike grid** | 12 JC stations | GBFS bike/dock counts |

**Liberty Light Rail** and **Exchange Pl** share a row above **JC Medical Center** (own row at the bottom); long titles use two lines (`Liberty` / `Light Rail`, `JC` / `Medical Center`).

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

From JC subway cards use **single-line** rows; long headsigns truncate with `…` like other stations.
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

**World Trade Center subway:** uses direct E-line arrivals when available. If not, estimates from **Canal St** WTC-bound departures **+2 min** (shown with `~` and note “est. Canal St + 2 min”). Cards show **up to 2 ETAs per line** when multiple lines serve the station. The **PATH WTC** card (tag `NJ`) sits in this section next to the subway tiles, and includes **Hoboken-bound** PATH trains on the **WTC–Hoboken** line.

**LSP area travel — change at Exchange Place:** Trips near **Liberty State Park** should **change at Exchange Place** (**HBLR → PATH**, same station complex). On **HBLR↔PATH**, watch **LSP HBLR +11 min** then **Exchange Place PATH → WTC** (and **PATH + Subway via WTC** uses the same Exchange → WTC leg). **Weekends through ~9 PM**, only if Exchange timing is poor: **northbound HBLR** to **Hoboken Terminal** and the **WTC–Hoboken** PATH shuttle (**Hoboken-bound** at **World Trade Center** on this tab).

### JC HBLR ↔ PATH

**Near Liberty State Park:** **change at Exchange Place** — HBLR and PATH share the same station (light rail upstairs, PATH downstairs). Use the **HBLR → PATH** section below (**LSP +11 min** → **Exchange Place PATH → WTC**). Weekend **WTC–Hoboken** via Hoboken Terminal is an alternate only when Exchange timing is poor.

Four connection sections (primary departures + catchable secondary after the offset):

| Section | Primary | Secondary (after offset) | Offset |
|---------|---------|--------------------------|--------|
| **HBLR → PATH** | Liberty State Park HBLR (once, full width) | **Exchange Place** → WTC · Newport → 33rd (side by side; **change at Exchange Place**) | 11 / 21 min |
| **PATH WTC → HBLR** | World Trade Center PATH (NJ-bound) | Exchange Place HBLR → Liberty State Pk | 7 min |
| **PATH 33rd St → HBLR** | Christopher St PATH (NJ-bound) | Newport HBLR → Liberty State Pk | 13 min |

**HBLR → PATH:** **Exchange Place** is the main interchange for LSP-area trips — the **Exchange Place → WTC** PATH card (left column under **HBLR → PATH**) lists departures **catchable after LSP +11 min**. **Newport → 33rd** (+21 min) is the alternate PATH side column. PANYNJ first, then **Transit API** (filter pool **8**). Cards stay empty when nothing is reachable from LSP — no misleading raw PATH ETAs.

**PATH → HBLR:** secondary HBLR uses **Transit App → PDF** (NJT live middle step unavailable — see below). **PATH WTC → HBLR** returns via **Exchange Place HBLR → Liberty State Pk** (+7 min). If nothing is catchable, live boards show **current HBLR** (`· current HBLR`).

**Exchange Place + LSP:** **Exchange Place** is the usual **HBLR ↔ PATH** transfer for the LSP area — ride **HBLR from Liberty State Park to Exchange Place**, then **change** to PATH toward **WTC** or **33rd St** (same complex; no street transfer). The app’s **HBLR → PATH** and **PATH + Subway via WTC** cards are timed for that **change at Exchange Place** (+11 min walk/connection from LSP HBLR).

**WTC–Hoboken PATH (weekends through ~9 PM):** **Not** the primary LSP route — use **Exchange Place** first (above). On **weekend** service (roughly **noon–9 PM**), if Exchange PATH timing is tight, an alternate is **northbound HBLR** from LSP to **Hoboken Terminal**, then the **WTC–Hoboken** PATH shuttle (**Hoboken-bound** trains at **World Trade Center** on **To JC**). Separate from **Newark-line** WTC departures at **Exchange Place** in weekend sync tests (20‑min **8th St** HBLR pairing).

**PATH + Subway via WTC:** first row — **Exchange Place** PATH → WTC (raw PANYNJ realtime, no LSP offset). Second row — **WTC Cortlandt** / **WTC** northbound subway, catchable after **LSP HBLR +11** then **Exchange PATH +8** walk at WTC. When PANYNJ or the subway API pool is too shallow, **Transit API** retries Exchange PATH and/or WTC subway stops (filter pool **8**); otherwise **current subway** (`· current subway`).

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
| **PATH + Subway via WTC** | **Exchange Place** PATH → WTC | **Primary** PANYNJ realtime (no offset); up to **3** ETAs |
| **PATH + Subway via WTC** | Exchange PATH timing (LSP chain) | **Transfer retry** — LSP **+11** chain, then Transit `PATH:554` if needed |
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
  debug_citibike_inactive.py      # Full UI; skip GBFS (placeholder dock cards)
  debug_path_inactive.py          # Full UI; skip PATH / PANYNJ
  debug_subway_inactive.py        # Full UI; skip subway APIs
  debug_hblr_inactive.py          # Full UI; skip HBLR↔PATH tab
  lib/
    path_trains.py                # PATH NYC / 33rd / NJ (PANYNJ single-fetch; Hoboken-terminating filtered, via-Hoboken kept, WTC allows Hoboken)
    hblr_path.py                  # HBLR↔PATH tab: four transfer pairs + offset filter
    mt_to_jc.py                   # MT→JC tab: subway → PATH (Nwk/JSQ/Hoboken) → HBLR southbound chains
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
    http_cache.py                 # 2 min persistent HTTP JSON cache (all API fetches)
    debug_flags.py                # BIKE_TRAIN_TRANSIT_INACTIVE env (debug entrypoints)
    lan_debug_server.py           # LAN debug HTTP server
  tests/                          # Unit tests (HBLR, PATH transfers, MT→JC chains, weekend sync, From JC express-local)
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
| `/status.json` | App state (stations, transit boards, active tab, errors, **`httpCache` hits/misses**) |
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

### Debug entrypoints (isolate data sources)

Run the **full UI** with one feed disabled (logs include `debug: … inactive`):

| Script | Disabled |
|--------|----------|
| `debug_citibike_inactive.py` | Citibike GBFS — placeholder dock cards |
| `debug_path_inactive.py` | PATH / PANYNJ — all PATH tabs empty |
| `debug_subway_inactive.py` | Subway APIs — From/To JC subway + WTC chain |
| `debug_hblr_inactive.py` | HBLR↔PATH tab |

Combine on PC: `python bike_train_transit.py --cli --inactive subway --inactive path`  
Or env: `BIKE_TRAIN_TRANSIT_INACTIVE=subway,path`  
LAN `/status.json` includes `"inactive": "subway, path"` when set.

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
| `path_trains.py` | PATH stations; PANYNJ `ridepath.json`; `_is_mt_to_jc_path_destination()` (Nwk/JSQ/Hoboken); `get_path_transit_board()` for transfer retry (`PATH:554` Exchange, `PATH:520` Newport, `PATH:553` WTC, `PATH:552` Chris St, `PATH:551` 9 St) |
| `mt_to_jc.py` | MT→JC three rows; chained offsets; PATH Hoboken on **9 St**, **Chris St**, and **WTC** cards (`allow_hoboken=True`); Transit retry for PATH and HBLR |
| `light_rail.py` | HBLR station boards by direction; Transit API key (`transit_credentials.json` / `TRANSIT_API_KEY`); optional NJT creds (`njt_credentials.json`) — **NJT dev API currently unavailable**; PDF fallback via `hblr_schedule_data.json` |
| `transit_app.py` | Transit App v4 `/stop_departures` client; uses shared `http_cache.py` (2 min, persistent) |
| `http_cache.py` | Persistent JSON cache for all HTTP fetches (GBFS, PANYNJ, subway, Transit) |
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
| UI stuck on “Updating…” / black screen | Transit fetch may be slow on the main thread (UI freezes until done). Check log for `step: fetch bikes` → `step: transit ok` → `finish render done`; redeploy latest code |
| Open shows empty data on launch | Expected until you tap a tab (log: `kickoff: poll (tap tab to load)` then `Refresh tab …`). Run as **main script** (Home Screen direct URL, not `RunBikeTrainTransit.py`) |
| Title overlaps the iOS status bar / notch | Layout uses `safe_area_insets.top` on iPhone 12+; fallback `TOP_CONTENT_INSET` (`43`) if unavailable |
| App drops to safe mode during auto-refresh | Native crash from background-thread TLS on older builds. Latest code fetches on the **main thread** only (no `@ui.in_background`, no refresh `threading.Thread`); `lib/parallel.py` runs transit jobs **sequentially** on Pythonista |
| Thumb float tabs stay grayed | Expected while `Updating…` is shown — tabs re-enable when kickoff refresh finishes (`thumb float armed 5s` in log) |
| Thumb float vanishes immediately after load | Expected on older builds that started the 5s timer before refresh finished. v49+ arms the timer **after** refresh completes |
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
| `lib/transit_app.py` | [Transit App API v4](https://api-doc.transitapp.com/v4.html) `/stop_departures` — **HBLR↔PATH tab only** (see [Transit App API usage](#transit-app-api-usage)); 2 min persistent cache via `http_cache.py` |
| `lib/path_trains.py` | PANYNJ [ridepath.json](https://www.panynj.gov/bin/portauthority/ridepath.json) (primary, one fetch); [path.api.razza.dev](https://path.api.razza.dev/) fallback if PANYNJ fails |
| `lib/light_rail.py` | Transit App (primary HBLR live) → NJT Bus/Light-Rail API (supported in code; **dev tokens currently unavailable**) → `hblr_schedule_data.json` PDF |
| `lib/subway_trains.py` | [subwayinfo.nyc](https://subwayinfo.nyc/) arrivals API |
| `lib/tunnel_crossings.py` | PANYNJ [crossingtimesapi.json](https://www.panynj.gov/bin/portauthority/crossingtimesapi.json) |
