# Initial Database Audit (baseline before changes)

MySQL 8.0.39 reachable at 127.0.0.1:3307 as `root@localhost` (full privileges). Charset utf8mb4.

| Object | Rows | Verified |
|---|---:|---|
| raw_rental_listings | 268,850 | ✔ 51 text columns, `NA` tokens |
| raw_mietenspiegel | 88 | ✔ |
| raw_mietenspiegel_metadata | 1 | ✔ reference date 2025-04-01 |
| raw_residential_locations | 26,205 | ✔ indexes on street, class |
| stg_hamburg_listings | 3,759 | ✔ 0 missing base rent/area/rent_per_sqm; €4.35–€61.25; 94 neighbourhoods; no duplicate scoutId |
| fact_mietenspiegel_benchmarks | 88 | ✔ exists, 88 rows, PK only (secondary indexes skipped as instructed) |
| analytics_hamburg_rental_market | – | **did not exist** |

Observations: staging street fields keep HTML entities (`&ouml;`); `streetPlain` has replacement characters in some rows; staging/fact tables use `utf8mb4_0900_ai_ci` while raw tables use `utf8mb4_unicode_ci`. No dedicated read-only account existed. Scripts inventory (11) matched the stated list and were backed up to `scripts/legacy_backup/`.

Housekeeping: the OpenAI key found in the specification file was moved to the git-ignored `.env` and redacted from the spec; it should still be **rotated** because it was exposed in plain text.
