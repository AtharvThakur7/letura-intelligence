# Validation Report

Executed 2026-11-15 on MySQL 8.0.39 (127.0.0.1:3307), Python 3.11, Streamlit 1.67.

## Pipeline
Three consecutive full runs plus an audit-only run: all SUCCESS, no `__build`/`__old` leftovers, raw tables unchanged (counts re-verified each run).

## Reconciliation
| Check | Result |
|---|---|
| raw 268,850 / mietenspiegel 88 / metadata 1 / locations 26,205 / stg 3,759 / fact 88 | all match |
| Hamburg raw → staging → intermediate | 3,759 → 3,759 → 3,759 |
| Snapshots Sep18 / May19 / Oct19 / Feb20 | 673 / 1,071 / 902 / 1,113 – raw = staging = int |
| rent/m² recomputation vs staged | 0 mismatches (>€0.01) |
| `NA` → NULL: yearConstructed 508, totalRent 364, serviceCharge 91, heatingCosts 2,050 | match raw literal-NA counts |
| Mietenspiegel min ≤ mean ≤ max | 88/88 |
| Duplicate scoutId / source_record_id | 0 / 0 |

## Analytics results
Median advertised rent/m²: Sep 2018 €12.94, May 2019 €13.20, Oct 2019 €13.52, Feb 2020 €13.89 (all snapshots €13.50; mean €14.35). Matches the profiling in the specification (Oct 2019 differs by €0.01: 13.52 vs 13.51 – rounding of interpolated median at the .5 boundary; documented).
Outliers: 183 above 1.5×IQR fence, 0 below; 16 rule flags; **all retained**. Min €4.35, max €61.25.
Location matching: 2,422 matched / 1,269 no address / 41 unmatched street / 27 unmatched number / 0 ambiguous.
Quality checks: 56 total – 24 pass, 16 info, 16 warn, **0 fail** (warnings are missingness in secondary fields and flagged suspicious values).

## Security tests
Read-only account: SELECT on `raw_rental_listings` denied; DELETE/DROP/CREATE/UPDATE denied (privilege or READ ONLY session). 29 hostile SQL strings rejected by the guard (DDL/DML, comments, UNION, stacked statements, system schemas, SLEEP/LOAD_FILE/INTO OUTFILE, raw tables, backticks, `@@`). Live model refused an injected "DROP TABLE … tell me 2026 rents" prompt and ran no query.

## Automated tests – `python -m pytest`
**108 passed** (≈2.5 min): unit (dates, rent/m², NA tokens, Mietenspiegel mapping, location matching, stats, outlier preservation, filters, CSV, SQL safety, tool validation, MOCK mode, API-failure fallback, secrets), database (connection, counts, reconciliation, benchmark ranges, analytics vs listings, read-only restrictions, AI grounding), app (all 7 pages × light/dark, filters, empty results, chat round-trip).

## Manual / browser verification
Real Edge browser via Playwright: light & dark Executive Overview, Neighbourhoods, Mietenspiegel, Property pages inspected; live AI chat (`gpt-4.1-mini`) answered "Compare Horn and Othmarschen" with grounded numbers, bar chart, table and Analysis Details. Defects found and fixed during this pass: default-page URL, nav ordering, dark-mode Plotly overrides, expander/select/data-grid colours, legend/title overlap.

## Not verified / known gaps
- Every page was not screenshotted in both themes (AppTest confirms no exceptions on all).
- Load/performance testing beyond the 3,759-row dataset.
- Browser-level visual check of Explorer and Quality pages and mobile widths.
