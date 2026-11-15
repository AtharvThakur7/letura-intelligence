# Final Project Audit

## Built
Idempotent MySQL pipeline (`scripts/run_pipeline.py`), analytics tables/views, seven-page Streamlit app (light/dark), database-grounded OpenAI analyst with MOCK/fallback, 108 automated tests, full documentation.

## Run it
```powershell
.\.venv\Scripts\activate
python scripts\run_pipeline.py
streamlit run app\main.py
python -m pytest
```

## Status
| Feature | Status |
|---|---|
| Source data preserved, counts reconcile | Completed, verified |
| Outliers retained and flagged | Completed, verified |
| Historical vs 2025 data separated with caveats | Completed |
| Dashboard metrics from MySQL; filters; CSV exports | Completed, tested |
| AI grounded in query results; follow-ups; charts; filters | Completed, tested live and mock |
| Unsafe SQL blocked; read-only account | Completed, tested |
| Mock mode without key | Completed, tested |
| Tests | 108 passed |
| Location enrichment | Partial – 64.4% matched; rest lack addresses/match |
| Visual QA | Partial – not every page in both themes; no mobile check |
| Key rotation | Needs user action |

## Limitations
See `docs/DATA_SOURCES_AND_LIMITATIONS.md`. Principal ones: 2018–2020 asking rents (not 2026 prices), independent snapshots, no coordinates, 419-row Wohnlagen discrepancy unexplained.
