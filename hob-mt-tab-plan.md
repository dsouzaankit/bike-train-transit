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
2. Port Authority bus terminal ETAs (bus 126, 119, 123) with gate nos.
3. NYC Subway next catchable ETAs (`+4 + <NY-Lincoln-eta-from-tunnels-tab>` min offset):
   - Filters: E to Queens, C northbound, 7 to Queens (**+5 min** offset)
   - A northbound ETA at `50 St`
   - 6 at `Grand Central-42 St` next catchable (chained, **+8 min** offset) north+south
   - 4/5 northbound ETAs at `51 St` + southbound ETAs at `33 St`
4. NY Waterway `Hoboken 14th Street` ETAs to Midtown/W39th — ref above
5. MTA bus next catchable ETAs (**+15 min** offset): routes **M42**, **M50** from `12 Av/W 42 St` (Plus Code QX6X+XG New York)

Default to current ETAs if previous in chain returns null.
