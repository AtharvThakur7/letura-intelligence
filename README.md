# Letura Intelligence – Hamburg Rental Market Analytics

A database-backed market-intelligence application: MySQL data pipeline → analytics tables → a seven-page Streamlit dashboard (light & dark mode) → an OpenAI-powered analyst that answers questions from real query results.

> **Data scope.** Rental listings are **historical advertised cold rents (Sep 2018 – Feb 2020)** – four independent snapshots, not current 2026 prices. The Hamburg **Mietenspiegel 2025** is an official reference table (ref. date 1 Apr 2025). They are different concepts and are never presented as a same-period premium or legal rent determination.

## Quick start (Windows)

```powershell
cd C:\Letura_Intelligence
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # skip if .env already exists; then edit values (never commit .env)
python scripts\run_pipeline.py
streamlit run app\main.py
```

Open http://localhost:8501. Toggle **Dark mode** in the sidebar.

## Prerequisites

| Item | Requirement |
|---|---|
| Python | 3.11+ |
| MySQL | 8.0 on `127.0.0.1:3307`, database `letura_intelligence`, already containing the raw tables (see below) |
| `.env` | DB credentials; optional OpenAI settings |

Raw tables expected (loaded by the original scripts in `scripts/`, **do not re-run them** – they refuse to load twice): `raw_rental_listings` (268,850), `raw_mietenspiegel` (88), `raw_mietenspiegel_metadata` (1), `raw_residential_locations` (26,205), plus `stg_hamburg_listings` (3,759) and `fact_mietenspiegel_benchmarks` (88).

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Admin connection used **only by the pipeline** |
| `AI_DB_USER`, `AI_DB_PASSWORD` | Dedicated SELECT-only account used by the dashboard and AI. Created/updated by the pipeline |
| `OPENAI_API_KEY` | Your key (local only; never displayed or logged) |
| `OPENAI_MODEL` | Model name, e.g. `gpt-4.1-mini` (changeable without code edits) |
| `AI_ENABLED` | `true` = use OpenAI when a valid key exists; `false` = MOCK mode |
| `AI_MAX_OUTPUT_TOKENS` | Cap per model response (default 800) |
| `AI_QUERY_TIMEOUT_SECONDS` | MySQL statement timeout (default 15) |

## Pipeline

```powershell
python scripts\run_pipeline.py                 # full, idempotent build
python scripts\run_pipeline.py --audit-only    # connect + verify counts, no writes
python scripts\run_pipeline.py --dry-run       # compute in memory, no writes
python scripts\run_pipeline.py --skip-locations
```

Steps: connection test → source audit & counts → verify staging → verify/build Mietenspiegel fact → enriched listings (+ optional Wohnlagen address matching) → analytics tables → quality checks → AI view & read-only grants → reports (`reports/data_quality_report.md`, `reports/data_quality_checks.csv`). Logs go to `logs/pipeline/`. Raw and staging tables are never modified; derived tables are built as `<name>__build` and swapped in atomically.

Objects created: `int_hamburg_listings`, `analytics_hamburg_rental_market`, `analytics_hamburg_neighbourhoods`, `analytics_hamburg_property_insights`, `analytics_mietenspiegel_reference`, `analytics_location_matching`, `analytics_data_quality`, `meta_pipeline_runs`, view `v_ai_listings`.

## Dashboard pages

1. **Executive Overview** – KPIs, snapshot trend, distributions, top neighbourhoods
2. **Rental Market Explorer** – distributions, scatter, box plots, amenities, searchable listing table + CSV
3. **Neighbourhood Analysis** – rankings with sample-size guard, comparisons, Bezirk view, normal vs good Wohnlage
4. **Property Insights** – size, rooms, construction year, type, amenities, new vs existing (associations only)
5. **Mietenspiegel Benchmark** – characteristic-based official reference rents and range charts
6. **Data Quality & Pipeline** – reconciliation, missing values, duplicates, outliers, pipeline runs, limitations
7. **AI Rental Analyst** – chat, suggested questions, charts, tables, "Analysis Details"

Sidebar filters (snapshot, neighbourhood, type, rooms, area, construction year, amenities) apply to pages 1–4 and the AI analyst.

## AI analyst

* **Live mode**: `AI_ENABLED=true` + valid `OPENAI_API_KEY`. The model can only call approved tools (`get_market_summary`, `get_rent_trends`, `compare_neighbourhoods`, `analyse_property_characteristics`, `get_rent_distribution`, `get_mietenspiegel_benchmark`, `get_data_quality_report`, guarded `run_readonly_sql`).
* **MOCK mode**: automatic when the key is missing/placeholder or `AI_ENABLED=false`. Deterministic routing to the same tools; no API calls. Also the automatic fallback if OpenAI is unavailable (credits, rate limit, network) – a notice explains why.
* Choose **Use active dashboard filters** or **Independent** on the AI page; a banner always states which scope is in force.

See [docs/AI_ANALYST_DESIGN.md](docs/AI_ANALYST_DESIGN.md).

## Tests

```powershell
python -m pytest              # all (database tests auto-skip if MySQL is unreachable)
python -m pytest tests\test_unit.py
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Database unavailable" banner | Start MySQL; check `DB_HOST/PORT/USER/PASSWORD` in `.env` |
| "Could not load listings" | Run `python scripts\run_pipeline.py` |
| `cryptography` error on connect | `pip install cryptography` |
| AI page says MOCK mode | Set `AI_ENABLED=true` and a valid `OPENAI_API_KEY`; restart Streamlit |
| "credits exhausted"/"rate limit" notice | Fallback answers are still database-grounded; top up credits or wait |
| Theme looks stale after code edits | Restart `streamlit run` (Streamlit does not hot-reload shared modules) |
| Pipeline: "Source count mismatch" | A raw table changed; it stops before any write – investigate before proceeding |

## Project layout

```
app/            Streamlit entry point (main.py), shared sidebar/theme, views/p1…p7
letura/         config, db, analytics (stats, transforms, repo, filters), pipeline (build), ai (tools, sqlguard, analyst, mock), ui
scripts/        run_pipeline.py + original ingestion scripts (legacy_backup/ holds copies)
tests/          unit, database and app tests
docs/ reports/  documentation, audits, generated quality reports
```

## Security notes

Secrets live only in `.env` (git-ignored). The dashboard/AI use a SELECT-only MySQL account limited to approved views/tables, READ ONLY sessions, statement timeouts and row caps. Model-proposed SQL is validated (single SELECT, approved tables, no comments/UNION/system schemas). No model-generated code is ever executed. **Rotate any API key that was ever pasted into chat or a document.**
