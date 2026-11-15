# Architecture

## Layers

```
raw_*  (never modified)  →  stg_hamburg_listings (validated, 3,759)  →  int_hamburg_listings (enriched, flags, location match)
raw_mietenspiegel(+metadata) → fact_mietenspiegel_benchmarks (88)
                                           ↓
              analytics_* tables  +  v_ai_listings view  +  analytics_data_quality  +  meta_pipeline_runs
                                           ↓  (SELECT-only account letura_ai_readonly, READ ONLY sessions)
                       letura.analytics.repo  →  Streamlit pages (app/views/p1…p7)
                                           ↓
                 letura.ai.tools (approved, validated tools) ← letura.ai.analyst (OpenAI | MOCK) ← Streamlit chat
```

## Packages

| Package | Responsibility |
|---|---|
| `letura/config.py` | `.env` loading; secrets held as `SecretStr` (never printed) |
| `letura/db.py` | admin engine (pipeline only) and read-only engine (dashboard/AI) with `READ ONLY` + `MAX_EXECUTION_TIME` |
| `letura/analytics/stats.py` | median, mean, P25/P75/P90/P95, IQR, outlier **flags**, Spearman (no SciPy) |
| `letura/analytics/transforms.py` | date parsing, NA tokens, rent/m², banding, neighbourhood→Bezirk, Mietenspiegel mapping, address normalisation and conservative Wohnlage matching |
| `letura/analytics/repo.py`, `filters.py` | cached data access; shared `FilterState` used by pages and AI |
| `letura/pipeline/build.py` | atomic build-and-swap of derived tables, quality checks, AI view/grants |
| `letura/ai/` | `tools.py` (8 tools, Pydantic args), `sqlguard.py`, `analyst.py` (orchestrator), `mock.py` |
| `letura/ui/` | `theme.py` (light/dark tokens, Plotly styling), `components.py` (KPI cards, charts, tables), `ai_render.py` |
| `app/` | `main.py` (navigation), `shared.py` (theme toggle, sidebar filters), `views/` (seven pages) |

## Key design decisions

1. **Percentiles in Python, not SQL.** MySQL 8 has no `PERCENTILE_CONT`; `stats.py` is the single implementation used by the pipeline, dashboard and AI so all numbers agree.
2. **Outliers flagged, never removed.** `outlier_iqr_global`, `outlier_iqr_snapshot` and `quality_flags` are extra columns; every analysis keeps all 3,759 rows.
3. **Atomic swaps.** Derived tables are built as `<name>__build`, validated, then `RENAME TABLE` swapped; raw/staging names are protected in code.
4. **Defence-in-depth for AI.** Tool whitelist → Pydantic validation → SQL validator → SELECT-only DB account → READ ONLY session → timeout → row cap.
5. **Filters apply identically** to the dashboard and the AI (same `FilterState`/`apply_filters`).
6. **Theming.** CSS variable tokens for light/dark; Plotly figures styled from the same tokens (`theme=None` so Streamlit does not override them).
