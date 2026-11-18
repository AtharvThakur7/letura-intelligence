# Letura Intelligence – Hamburg Rental Market Analytics

A database-backed market-intelligence application: MySQL data pipeline → analytics tables → a seven-page Streamlit dashboard (light and dark modes) → an OpenAI-powered analyst that answers questions using real query results.

**Project links:** [Live Demo](https://mainpy-tsmwzgucehnwtfmxknjxjf.streamlit.app/) · [GitHub Repository](https://github.com/AtharvThakur7/letura-intelligence) ·
[Download Project Overview (PDF)](docs/Letura_Project_Overview.pdf)

> **Data scope:** Rental listings are historical advertised cold rents (September 2018–February 2020), across four independent snapshots—not current 2026 prices. The Hamburg Mietenspiegel 2025 is an official reference table (reference date: 1 April 2025). These are different concepts and are not presented as a same-period premium comparison or legal rent determination.

## Quick start (Windows)

```powershell
cd C:\Letura_Intelligence
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # Skip if .env exists; edit values locally.
python scripts\run_pipeline.py
streamlit run app\main.py
```

Open http://localhost:8501. Toggle **Dark mode** in the sidebar.

## Prerequisites

| Item | Requirement |
|---|---|
| Python | 3.11+ |
| MySQL | 8.0 at `127.0.0.1:3307`; database `letura_intelligence` |
| `.env` | Database credentials; optional OpenAI settings |

The following raw and staging tables must already exist. They were loaded by the original scripts in `scripts/`. **Do not rerun those ingestion scripts**; they refuse to load data twice.

| Table | Expected rows |
|---|---:|
| `raw_rental_listings` | 268,850 |
| `raw_mietenspiegel` | 88 |
| `raw_mietenspiegel_metadata` | 1 |
| `raw_residential_locations` | 26,205 |
| `stg_hamburg_listings` | 3,759 |
| `fact_mietenspiegel_benchmarks` | 88 |

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Admin connection used only by the pipeline |
| `AI_DB_USER`, `AI_DB_PASSWORD` | Dedicated SELECT-only account for dashboard and AI; created/updated by pipeline |
| `OPENAI_API_KEY` | API key; local only, never displayed or logged |
| `OPENAI_MODEL` | Model name, e.g. `gpt-4.1-mini`; configurable without code edits |
| `AI_ENABLED` | `true` enables OpenAI with a valid key; `false` uses MOCK mode |
| `AI_MAX_OUTPUT_TOKENS` | Response token cap; default 800 |
| `AI_QUERY_TIMEOUT_SECONDS` | MySQL statement timeout; default 15 |

## Pipeline

```powershell
python scripts\run_pipeline.py                 # Full, idempotent build
python scripts\run_pipeline.py --audit-only    # Connect + verify counts; no writes
python scripts\run_pipeline.py --dry-run       # Compute in memory; no writes
python scripts\run_pipeline.py --skip-locations
```

Sequence: connection test → source audit/counts → staging verification → Mietenspiegel fact verification/build → enriched listings (optional Wohnlagen address matching) → analytics tables → quality checks → AI view/read-only grants → reports.

Reports: `reports/data_quality_report.md` and `reports/data_quality_checks.csv`. Logs: `logs/pipeline/`. Raw and staging tables are never modified. Derived tables are built as `__build` tables and swapped atomically.

**Created objects:** `int_hamburg_listings`, `analytics_hamburg_rental_market`, `analytics_hamburg_neighbourhoods`, `analytics_hamburg_property_insights`, `analytics_mietenspiegel_reference`, `analytics_location_matching`, `analytics_data_quality`, `meta_pipeline_runs`, and view `v_ai_listings`.

## App pages

The project is described as a seven-page dashboard. The supplied page inventory names these six pages; the seventh page's exact title and functionality should be confirmed before publishing a complete page-by-page inventory.

1. **Home:** Animated overview, clickable AI questions, Hamburg treemap.
2. **Market:** Headline metrics, rent trends and distributions.
3. **Neighbourhoods:** Rankings, comparisons, districts, location quality.
4. **Properties:** Size, building age, type and features; searchable listing table with CSV download.
5. **Official rents:** Hamburg Mietenspiegel 2025 reference rents alongside historical advertised rents.
6. **Ask AI:** Data-grounded chat with charts and Analysis Details.

Sidebar filters (period, neighbourhood, type, rooms, size, year built and features) appear on Market, Neighbourhoods, Properties and Ask AI. Data-quality results are written to `reports/data_quality_report.md` and `analytics_data_quality`, and are available to the AI analyst.

## AI analyst

**Live mode:** Set `AI_ENABLED=true` and provide a valid `OPENAI_API_KEY`. The model can call only approved tools:

- `get_market_summary`
- `get_rent_trends`
- `compare_neighbourhoods`
- `analyse_property_characteristics`
- `get_rent_distribution`
- `get_mietenspiegel_benchmark`
- `get_data_quality_report`
- Guarded `run_readonly_sql`

**MOCK mode:** Used when the key is missing/placeholder or `AI_ENABLED=false`. It routes deterministically to the same tools without API calls. If OpenAI is unavailable (credits, rate limit, network), the app falls back automatically and explains why.

Choose **Use active dashboard filters** or **Independent** on the AI page; a banner states the active scope. See `docs/AI_ANALYST_DESIGN.md`.

## Tests

```powershell
python -m pytest              # Full suite; DB tests auto-skip if MySQL is unreachable
python -m pytest tests\test_unit.py
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| “Database unavailable” | Start MySQL; check DB_HOST/PORT/USER/PASSWORD in `.env` |
| “Could not load listings” | Run `python scripts\run_pipeline.py` |
| `cryptography` connection error | `pip install cryptography` |
| AI page shows MOCK mode | Set `AI_ENABLED=true`, add a valid key, restart Streamlit |
| Credits exhausted/rate limit | Fallback remains database-grounded; top up credits or wait |
| Theme looks stale | Restart Streamlit; shared modules may not hot-reload |
| Source count mismatch | A raw table changed; pipeline stops before writes—investigate first |

## Project layout

```text
app/       Streamlit entry point, shared sidebar/theme, views/p1…p7
letura/    config, db, analytics, pipeline, AI tools/SQL guard/analyst/mock, UI
scripts/   run_pipeline.py and original ingestion scripts (legacy_backup/ has copies)
tests/     unit, database and app tests
docs/      technical documentation
reports/   generated data-quality reports
```

## Security notes

- Secrets live in `.env` (git-ignored).
- Dashboard and AI use a SELECT-only MySQL account limited to approved views/tables.
- Sessions are read-only and use statement timeouts and row caps.
- Model-proposed SQL is validated: single SELECT, approved tables, no comments/UNION/system schemas.
- Model-generated code is never executed.

**Security reminder:** Rotate any API key that was ever pasted into chat or a document.
