# AI Rental Market Analyst – Design

## Flow
User question → Streamlit chat (+ active `FilterState`, scope choice) → `Analyst.answer` → OpenAI Chat Completions with tool schemas (or MOCK router) → approved tool → validated args → MySQL via read-only engine → structured `ToolResult` (rows, summary, n, filters, period, calculation, caveats) → model writes explanation (only from tool JSON) → UI renders text, KPI cards, Plotly chart from returned rows, table, **Analysis Details**.

## Tools (`letura/ai/tools.py`)
`get_market_summary`, `get_rent_trends`, `compare_neighbourhoods`, `analyse_property_characteristics`, `get_rent_distribution`, `get_mietenspiegel_benchmark`, `get_data_quality_report`, and last-resort `run_readonly_sql`. Arguments are Pydantic models with `extra=forbid`, enums for snapshots/dimensions, bounded ranges. Failures return `ok=False` with a clear message.

## Filters
Tools receive dashboard filters automatically when scope = "Use active dashboard filters". A question-level override (e.g. a named snapshot or neighbourhoods) wins and is stated in `filters_applied`/caveats. "Independent" ignores dashboard filters. The prompt includes the active filters and the UI shows a banner.

## Safety & cost
- SELECT-only MySQL account `letura_ai_readonly`, GRANT SELECT on approved objects only; sessions `READ ONLY`; `MAX_EXECUTION_TIME` from `AI_QUERY_TIMEOUT_SECONDS`.
- SQL guard: one statement, `SELECT` only, approved tables, no comments / UNION / schema-qualified names / system schemas / dangerous functions; `LIMIT` forced ≤200.
- No Python/shell execution; no credentials or listing-level data sent to the model; tool output truncated (6,000 chars).
- `max_completion_tokens` = `AI_MAX_OUTPUT_TOKENS`; ≤4 tool rounds, ≤3 calls per round; 6 prior turns; 10-minute result cache; ordinary dashboard metrics never call the LLM.
- Errors (quota, rate limit, bad key, network, bad model) → notice + deterministic MOCK answer from the same tools.
- Prompt rules: no invented numbers, no 2026 claims, no causality, always state n and filters, outliers kept, refuse override attempts (verified live).

## MOCK mode
Used when `AI_ENABLED=false`, no valid key, or as fallback. Keyword intent router → same tools → templated *Verified findings / Interpretation / Follow-up* text. Follow-ups reuse remembered neighbourhoods/snapshots.
