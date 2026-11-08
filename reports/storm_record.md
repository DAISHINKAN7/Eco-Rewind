# Storm record check of event and placebo windows

Source: NOAA HURDAT2 `hurdat2-1851-2025-092326.txt` (best tracks to 2025). Radius 200 km around the AOI centre. A placebo window passes if no storm of ≥ 34 kt came within the radius.

| Cutoff | Kind | Window | Storms within radius (closest km, date, max wind kt) | Verdict |
|---|---|---|---|---|
| ida | event | 2021-07-01 → 2023-10-01 (cutoff 2021Q3, H ≤ 8) | IDA AL092021 (40 km, 2021-08-29, 130 kt); NICHOLAS AL142021 (89 km, 2021-09-16, 25 kt) | event window (storms expected) |
| irma | event | 2017-07-01 → 2018-07-01 (cutoff 2017Q3, H ≤ 3) | IRMA AL112017 (96 km, 2017-09-10, 115 kt) | event window (storms expected) |
| ida_placebo_2018 | placebo | 2018-07-01 → 2019-07-01 (cutoff 2018Q3, H ≤ 3) | none | ✅ clean |
| ida_placebo_2015 | placebo | 2015-07-01 → 2016-07-01 (cutoff 2015Q3, H ≤ 3) | none | ✅ clean |
| ida_placebo_2016 | placebo | 2016-07-01 → 2017-07-01 (cutoff 2016Q3, H ≤ 3) | none | ✅ clean |
| irma_placebo_2015 | placebo | 2015-07-01 → 2016-10-01 (cutoff 2015Q3, H ≤ 4) | HERMINE AL092016 (177 km, 2016-08-28, 30 kt) | ✅ clean |
| irma_placebo_2016 | placebo | 2016-07-01 → 2017-07-01 (cutoff 2016Q3, H ≤ 3) | HERMINE AL092016 (177 km, 2016-08-28, 30 kt) | ✅ clean |

**Placebo conflicts: none.** Any conflict must be resolved by the user (shorten max_horizon or replace the window) and re-registered.
