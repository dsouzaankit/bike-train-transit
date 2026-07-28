# HOB / NYC Citibike + HOB↔MT — plan

Layout diagram: [`thumb-float-layout-hob-nyc.svg`](thumb-float-layout-hob-nyc.svg)

## Decisions

- Pill / tab name: **HOB↔MT** (not HOB↔NYC)
- Citibike GBFS refreshes are **separate per tab** (Cbike JC / S JC / HOB / NYC each fetch only their station set on tap)
- NY Waterway ETA ref: https://etacloud.connexionz.net/nywaterway/eta/9 (platform/stop 9 = Hoboken 14th Street)

## HOB Citibike tab

- Madison St & 10 St
- Adams St & 12 St
- Grand St & 14 St
- Willow Ave & 12 St
- 14 St Ferry - 14 St & Shipyard Ln
- 12 St & Sinatra Dr N

## NYC Citibike tab

- 12 Ave & W 40 St
- 11 Ave & W 41 St
- W 44 St & 11 Ave
- W 52 St & 11 Ave
- W 54 St & 11 Ave

## HOB↔MT tab

1. NJT bus 126, 119 ETAs to NYC — Stop# 32084 (Willow Ave + 15th St)
   + PABT **departures** (119/123/126 leaving terminal toward NJ; Transit `stop_departures`)
   — Willow + PABT cards sit side-by-side
2. NYC Subway next catchable ETAs (`+4 + <NY-Lincoln-eta>` == primary **LincTnl** + walk **+4**; card note `LincTnl +4`):
   - Filters: E to Queens, 7 to Queens (**LincTnl +9** = +4 walk +5)
   - A northbound ETA at `50 St`
   - 6 at `Grand Central-42 St` next catchable (chained, **LincTnl +12** = +4 walk +8) north+south
   - 4/5 northbound ETAs at `51 St` + southbound ETAs at `33 St`
3. NY Waterway `Hoboken 14th Street` ETAs to Midtown/W39th — ref above
4. MTA bus next catchable ETAs (**+15 min** offset): routes **M42**, **M50** from `12 Av/W 42 St` (Plus Code QX6X+XG New York)
   (NY Waterway + MTA bus cards sit side-by-side)

Default to current ETAs if previous in chain returns null.
