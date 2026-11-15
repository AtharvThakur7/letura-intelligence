# Letura Intelligence — End-to-End Implementation Specification

## 1. Project objective

Build **Letura Intelligence – Hamburg Rental Market Analytics Platform**, a complete, working data engineering, business intelligence and AI application for a German residential rental company.

The project must include:

- Data cleaning and transformation.
- MySQL data integration.
- Data quality and validation.
- Rental market analytics.
- Interactive Streamlit dashboard.
- OpenAI-powered AI rental market analyst.
- Automated tests and complete documentation.

This is an implementation assignment. Claude Code must inspect the existing repository, make actual code changes, run tests and complete the project. Do not stop after creating a plan.

## 2. Existing data

### Dataset A — German rental listings

Source: `immo_data.csv`

- Raw records: 268,850.
- Hamburg records: 3,759.
- Table: `raw_rental_listings`.
- Period: September 2018–February 2020.
- Snapshots:
  - September 2018: 673.
  - May 2019: 1,071.
  - October 2019: 902.
  - February 2020: 1,113.

Important columns:

`baseRent`, `totalRent`, `livingSpace`, `noRooms`, `yearConstructed`, `typeOfFlat`, `balcony`, `garden`, `lift`, `hasKitchen`, `newlyConst`, `regio3`, `street`, `houseNumber`, `geo_plz`, `date`.

The Hamburg subset has no missing base rent, living space or room count according to previous profiling.

Other missing values:
- Construction year: 508.
- Total rent: 364.
- Service charge: 91.
- Heating costs: 2,050.

The source uses literal `NA` values.

Historical median advertised rent per m²:
- September 2018: €12.94.
- May 2019: €13.20.
- October 2019: €13.51.
- February 2020: €13.89.

These are independent snapshots, not longitudinal observations of the same properties. Never describe them as current 2026 rents.

### Dataset B — Hamburg Mietenspiegel 2025

Tables:
- `raw_mietenspiegel`: 88 records.
- `raw_mietenspiegel_metadata`: 1 record.

Contains:
- Reference rent.
- Minimum and maximum reference rent.
- Construction period.
- Equipment.
- Residential location.
- Living-area category.

Reference date: 1 April 2025.

The data represents official reference rents, excluding heating and operating costs. It is not an advertised-rent listing dataset.

### Dataset C — Hamburg Wohnlagenverzeichnis 2025

Table: `raw_residential_locations`.

- Loaded records: 26,205.
- PDF stated count: 25,786.
- Preserve all extracted records and document the 419-record discrepancy.
- Fields include street, house-number range, numbering type, location class and location score.
- Numbering types: U = odd, G = even, S = special.
- Location classes: normal and gut.

Location matching is optional and must not delay the rest of the application.

## 3. Existing project state

Project root:

`C:\Letura_Intelligence`

Database:

- MySQL 8.0.39.
- Host: `127.0.0.1`.
- Port: `3307`.
- Database: `letura_intelligence`.

Credentials must be read from `.env`, never hard-coded or printed.

Raw tables:

| Table | Records |
|---|---:|
| raw_rental_listings | 268,850 |
| raw_mietenspiegel | 88 |
| raw_mietenspiegel_metadata | 1 |
| raw_residential_locations | 26,205 |

### Completed transformation

`stg_hamburg_listings`

- 3,759 records.
- Missing base rent: 0.
- Missing living space: 0.
- Missing rent per m²: 0.
- Minimum rent per m²: €4.35.
- Maximum rent per m²: €61.25.
- Contains `listing_date` and `rent_per_sqm`.

This table has been successfully created and validated.

### Mietenspiegel transformation

The user says `fact_mietenspiegel_benchmarks` has been created.

The optional secondary indexes failed and were skipped. Do not waste time recreating them.

Verify that the table exists and contains 88 records before making changes.

### Next analytics script — not executed

The proposed `analytics_hamburg_rental_market` script was not executed.

Claude must inspect whether the table exists and implement the analytics properly, including median, percentiles and sample counts.

## 4. Important data principle

**Never remove outliers.**

Keep every original observation.

Unusual values may be genuine property listings. Flag them for investigation, but do not delete or silently replace them.

Use:
- Median.
- Mean.
- P25 and P75.
- P90/P95 where appropriate.
- IQR.
- Minimum and maximum.
- Sample counts.

## 5. First implementation task: audit existing work

Before coding:

1. Inspect all project files.
2. Inspect existing scripts and logs.
3. Inspect `.env` variable names without displaying values.
4. Connect to MySQL.
5. Inspect table schemas and row counts.
6. Verify `stg_hamburg_listings`.
7. Verify `fact_mietenspiegel_benchmarks`.
8. Check whether `analytics_hamburg_rental_market` exists.
9. Create `reports/initial_database_audit.md`.

Do not drop raw tables, rerun ingestion blindly or overwrite working scripts.

## 6. Technology stack

Use:

- Python.
- MySQL 8.
- SQLAlchemy.
- PyMySQL.
- Pandas and NumPy.
- Streamlit.
- Plotly.
- OpenAI Python SDK.
- Pydantic.
- python-dotenv.
- pytest.

Prefer a Streamlit-first local application. Do not introduce unnecessary infrastructure.

## 7. Required analytics datasets

Build these analytical tables or views:

1. `analytics_hamburg_rental_market`
2. `analytics_hamburg_neighbourhoods`
3. `analytics_hamburg_property_insights`
4. `analytics_mietenspiegel_reference`
5. `analytics_data_quality`

### Rental market analytics

By snapshot:
- Number of listings.
- Median rent per m².
- Average rent per m².
- P25/P75.
- Median base rent.
- Median living area.
- Median rooms.

### Neighbourhood analytics

By neighbourhood and snapshot:
- Listing count.
- Median advertised rent per m².
- Average advertised rent per m².
- P25/P75.
- Minimum/maximum.
- Median living space.
- Median rooms.

Show sample size and warn for small samples.

### Property analytics

Analyse:
- Apartment size.
- Room count.
- Construction year.
- Property type.
- Balcony.
- Garden.
- Lift.
- Kitchen.
- New construction.

Show missingness and coverage. Do not make causal claims.

### Mietenspiegel analysis

Allow filters for:
- Construction period.
- Equipment.
- Residential location.
- Living-area category.

Display official reference rent, range, publisher and date.

Clearly distinguish reference rents from advertised rents.

Any cross-period comparison must display:

"These datasets differ in reference period, population and methodology. This comparison is contextual, not a same-period market premium or legal rent determination."

## 8. Streamlit dashboard

Build a polished professional PropTech application named:

**Letura Intelligence**

Subtitle: Hamburg Rental Market Analytics.

Use a clean enterprise design, consistent typography, restrained colours, professional KPI cards and Plotly charts.

### Page 1 — Executive Overview

KPI cards:
- Total listings.
- Neighbourhoods.
- Median advertised rent per m².
- Median living space.
- Historical date range.

Charts:
- Historical snapshot trends.
- Neighbourhood comparison.
- Rent distribution.

### Page 2 — Rental Market Explorer

Filters:
- Date.
- Neighbourhood.
- Property type.
- Room count.
- Living area.
- Construction year.
- Amenities.

Charts:
- Rent distribution.
- Rent versus living area.
- Rent by room count.
- Rent by property type.

Include a searchable listing table and CSV download.

### Page 3 — Neighbourhood Analysis

Compare neighbourhoods using:
- Median rent.
- Mean rent.
- P25/P75.
- Listing counts.
- Box plots.
- Snapshot trends.

### Page 4 — Property Insights

Analyse apartment size, rooms, building age, type and amenities.

### Page 5 — Mietenspiegel Benchmarks

Provide interactive characteristic filters and official reference-rent comparisons.

### Page 6 — Data Quality & Sources

Display:
- Source inventory.
- Row counts.
- Missing values.
- Invalid values.
- Duplicates.
- Outlier flags.
- Data reconciliation.
- Known limitations.

### Page 7 — AI Rental Market Analyst

Create an interactive chat interface connected to the actual MySQL database and current dashboard filters.

## 9. AI analyst

Example questions:

- Which neighbourhood had the highest median rent in February 2020?
- Compare Horn and Othmarschen.
- What is the median rent per m² for two-room apartments?
- How many records have missing construction-year data?
- Show the Mietenspiegel range for a selected property characteristic.
- Explain the limitations of this dataset.

### Architecture

1. User asks a question.
2. Streamlit sends the question and active dashboard filters.
3. AI receives the schema and business definitions.
4. AI selects a predefined analytical function or proposes a read-only SQL query.
5. Application validates the query.
6. MySQL executes it using a read-only user.
7. Actual query results return to the AI.
8. AI explains the results.
9. Streamlit displays the answer, relevant metrics, source period and caveats.

### Security

- SELECT-only access.
- Approved tables/views only.
- Block all DDL and DML.
- Parameterise user inputs.
- Apply query timeouts and row limits.
- Never expose API keys or database credentials.
- Never execute model-generated Python.
- Do not allow arbitrary SQL execution.
- Prefer predefined analytics tools.
- Include mock mode so testing works without API credits.

The AI must never invent values or claim current 2026 rental prices based on 2018–2020 listings.

Use the official OpenAI SDK and keep the model configurable. Use a replacement API key stored locally in `.env`, not the key previously shared in chat.

The owner has limited API credits, so use bounded calls, conservative token limits and avoid LLM calls for ordinary dashboard metrics.

## 10. Optional location enrichment

If feasible, implement conservative address matching.

- Decode HTML entities.
- Normalize Unicode.
- Preserve raw street names.
- Match house-number ranges.
- Respect U/G/S numbering.
- Handle suffixes such as 9a.
- Preserve unmatched and ambiguous records.
- Never force matches.

Do not let this step block the rest of the application.

## 11. Pipeline

Create:

`python scripts/run_pipeline.py`

It should:
1. Test database connection.
2. Audit source tables.
3. Verify source counts.
4. Verify/build listing transformations.
5. Verify/build Mietenspiegel transformation.
6. Optionally run location enrichment.
7. Build analytics.
8. Run quality checks.
9. Generate reports.

The pipeline must be idempotent and must never destroy raw data.

Support audit-only/dry-run mode.

## 12. Tests

Use pytest to test:
- Database connection.
- Source counts.
- Date parsing.
- Rent-per-square-metre calculation.
- Missing token handling.
- Mietenspiegel parsing.
- Benchmark ranges.
- Outlier preservation.
- SQL safety.
- AI mock mode.
- Dashboard filters.
- CSV exports.
- Source-to-transformed reconciliation.

## 13. Documentation

Create:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_DICTIONARY.md`
- `docs/DATA_SOURCES_AND_LIMITATIONS.md`
- `docs/AI_ANALYST_DESIGN.md`
- `docs/VALIDATION_REPORT.md`
- `reports/initial_database_audit.md`
- `reports/final_project_audit.md`

README must explain Windows setup, virtual environment, dependencies, MySQL, `.env`, pipeline execution, Streamlit startup, AI configuration, testing and troubleshooting.

## 14. Configuration

Create `.env.example`:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3307
DB_NAME=letura_intelligence
DB_USER=your_mysql_user
DB_PASSWORD=replace_locally

OPENAI_API_KEY=replace_with_new_rotated_key
OPENAI_MODEL=choose_supported_model
AI_ENABLED=false
AI_MAX_OUTPUT_TOKENS=800
AI_QUERY_TIMEOUT_SECONDS=15
APP_ENV=local
```

Never overwrite the actual `.env`.

Add `.env`, `.venv`, `__pycache__`, `.pytest_cache` and logs to `.gitignore`.

## 15. Implementation phases

Phase 1: Audit and preserve existing work.

Phase 2: Complete transformations and analytics.

Phase 3: Optional location enrichment.

Phase 4: Build all Streamlit pages.

Phase 5: Implement AI analyst and safe database integration.

Phase 6: Run tests, validate all results and produce final audit.

Claude must continue through all phases rather than stopping after writing a plan.

## 16. Final deliverables

The completed project must include:

1. Working Streamlit application.
2. MySQL integration.
3. Reproducible data pipeline.
4. Rental market dashboard.
5. Neighbourhood analytics.
6. Property insights.
7. Mietenspiegel explorer.
8. Data quality page.
9. AI rental market analyst.
10. Automated tests.
11. Complete documentation.
12. Source and data dictionary.
13. Pipeline logs and quality reports.
14. Final audit report.
15. Exact commands to run the application and tests.

## 17. Definition of done

The project is complete only when:
- Existing source data is preserved.
- All transformations reconcile.
- Outliers remain.
- Historical and 2025 data are clearly distinguished.
- Dashboard metrics come from MySQL.
- Filters work.
- CSV exports work.
- AI answers are grounded in real query results.
- Unsafe SQL is blocked.
- Mock AI works without an API key.
- Tests pass or failures are documented.
- A new developer can run the project using the README.

**Claude Code instruction:** Start by inspecting the actual repository and database. Implement the phases, make real code changes, run validation after each phase, and continue until the project is working. Report exact results and clearly distinguish completed, partial and blocked features. Do not fabricate functionality or data.



this is company webiste which can use to inspect and see their business goal : https://letura.de/



this is openai api key you will need : <REDACTED - key moved to local .env; rotate this key>






# ADDITIONAL REQUIREMENTS: DASHBOARD DESIGN AND AI RENTAL MARKET ANALYST

## 1. Product Ownership and Implementation Instructions

Build the application according to the requirements below.

I am defining the business requirements and expected functionality. You are responsible for the technical implementation, architecture, SQL queries, Python code, UI/UX, charts, integrations and testing.

Do not leave dashboard design or AI functionality as placeholders.

Before implementing anything:
- Inspect the existing project structure, scripts, MySQL tables and existing transformations.
- Reuse existing working scripts and tables wherever possible.
- Do not unnecessarily recreate or overwrite existing data.
- Verify that the required data exists before designing individual visualisations.
- If a requested metric cannot be calculated from the available data, explain why and do not fabricate it.

The application should look and behave like a professional commercial real-estate market intelligence platform.

---

## 2. Dashboard Requirements

Build the following seven fully functional dashboard pages.

### PAGE 1: Executive Overview

Purpose: Provide a high-level understanding of the Hamburg rental market.

Required KPIs:
- Total rental listings.
- Median advertised cold rent per square metre.
- Average advertised cold rent per square metre.
- Median apartment living area.
- Median number of rooms.
- Number of listings across available snapshots.

Visualisations:
- Historical median rent per square metre across the four available snapshots.
- Rental price distribution.
- Listings by snapshot date.
- Distribution of apartment sizes.
- Distribution by number of rooms.
- Property type distribution.

Filters:
- Snapshot date.
- Neighbourhood.
- Property type.
- Number of rooms.
- Living area range.

All KPIs, charts and tables should respond to applicable filters.

### PAGE 2: Rental Market Explorer

Purpose: Explore rental prices and property characteristics in detail.

Visualisations:
- Rent per square metre distribution.
- Rent per square metre versus living area.
- Rent per square metre by number of rooms.
- Rent distribution by property type.
- Rent comparison by available amenities.
- Listings by snapshot.

Required features:
- Interactive filters.
- Sorting and searching.
- Listing-level data table.
- Outlier identification without deleting original records.
- Median, mean, percentiles and sample counts.

### PAGE 3: Neighbourhood Analysis

Purpose: Understand differences across Hamburg neighbourhoods.

Required analysis:
- Median advertised rent per square metre by neighbourhood.
- Average advertised rent per square metre by neighbourhood.
- Listing volume by neighbourhood.
- Comparison of neighbourhoods.
- Available residential location classifications.
- Normal versus good residential location comparisons.

Visualisations:
- Neighbourhood comparison bar chart.
- Rent distribution by neighbourhood.
- Neighbourhood ranking table.
- Geographic visualisation only where reliable geographic data is available.

Do not invent neighbourhood-level results or assign a residential classification where the address cannot be matched reliably.

### PAGE 4: Property Insights

Purpose: Identify relationships between property characteristics and advertised rent.

Analyse:
- Construction year versus rent per square metre.
- Apartment size versus rent.
- Number of rooms versus rent.
- Property type versus rent.
- Balcony, garden, lift and kitchen availability.
- Newly constructed versus existing properties.

Visualisations:
- Scatter plots.
- Box plots.
- Bar charts.
- Distribution charts.
- Interactive property listings.

Do not describe an observed relationship as causal.

### PAGE 5: Mietenspiegel Benchmark

Purpose: Compare historical rental listing observations with official Hamburg Mietenspiegel 2025 reference data.

Required features:
- Reference mean rent per square metre.
- Minimum and maximum reference rent.
- Construction period.
- Equipment classification.
- Residential location classification.
- Living-area category.
- Characteristic-based benchmark selection.

Visualisations:
- Benchmark range comparison.
- Historical listing rent versus official reference rent.
- Comparisons by available benchmark characteristics.

Important business rules:
- Historical rental listings are from 2018–2020.
- Mietenspiegel data refers to 2025.
- Advertised cold rent and official Mietenspiegel reference rent are different concepts.
- Do not present these comparisons as same-period market premiums, legal valuations or current 2026 rental prices.
- Display the source and reference date clearly.

### PAGE 6: Data Quality and Pipeline Monitoring

Purpose: Demonstrate reliable data engineering and data governance.

Display:
- Raw and transformed record counts.
- Missing-value percentages.
- Duplicate checks.
- Invalid or suspicious values.
- Rent per square metre outlier flags.
- Snapshot-level record counts.
- Transformation status.
- Source data coverage.
- Data reconciliation issues.

Include:
- Data-quality KPI cards.
- Missing-value charts.
- Data profiling tables.
- Pipeline execution status.

Preserve original source records. Outlier identification must not automatically delete records.

### PAGE 7: AI Rental Market Analyst

Purpose: Provide a conversational AI interface that can analyse the underlying rental market data.

This is a core feature, not an optional chatbot.

Build a dedicated AI page with:
- Chat interface.
- Conversation history within the session.
- Suggested business questions.
- Context-aware analysis.
- Dynamic charts where appropriate.
- Tables for detailed answers.
- Clear explanations of the data used.

---

## 3. AI Rental Market Analyst: Core Requirements

### 3.1 Role of the AI

The AI should behave as a professional Real Estate Data Analyst and Market Intelligence Analyst specialising in Hamburg rental market data.

It should understand:
- Rental listing data.
- Rent per square metre.
- Property characteristics.
- Neighbourhood comparisons.
- Historical snapshots.
- Residential location classifications.
- Hamburg Mietenspiegel 2025.
- Data quality and limitations.

It should answer questions using actual database results rather than relying on general LLM knowledge.

### 3.2 Example questions the AI must support

Market analysis:
- What is the median advertised rent per square metre in Hamburg?
- How did median advertised rent change across the available snapshots?
- Which neighbourhoods have the highest median advertised rents?
- Which neighbourhoods have the most rental listings?
- What is the rent distribution across the dataset?

Property analysis:
- Do larger apartments have lower advertised rent per square metre?
- How does rent differ between apartments with and without balconies?
- Compare properties with two rooms and three rooms.
- What is the relationship between apartment size and advertised rent?
- Which property types have the highest median rent per square metre?

Benchmark analysis:
- Explain the Hamburg Mietenspiegel 2025.
- Compare a selected benchmark range with historical listing observations.
- What are the differences between normal and good residential locations?
- Explain the limitations of comparing historical listings with 2025 reference rents.

Data quality:
- Which columns have the most missing values?
- How many records are available for each snapshot?
- Are there suspicious rent-per-square-metre values?
- Explain the data-quality limitations of this dataset.

Business questions:
- Summarise the key findings from the available Hamburg rental data.
- Which neighbourhoods should be investigated further?
- What factors appear associated with higher advertised rents?
- Prepare an executive summary of the available market data.

The AI should also support relevant follow-up questions using conversation context.

### 3.3 AI Architecture

Implement the following architecture:

User question
    ↓
Streamlit AI Chat Interface
    ↓
Python AI Orchestration Layer
    ↓
OpenAI API
    ↓
Approved Analytics Tools / Database Query Layer
    ↓
MySQL Analytics Views and Tables
    ↓
Query Results
    ↓
OpenAI Analysis and Explanation
    ↓
Final Answer + Table / Chart

Use the official OpenAI Python SDK and a suitable model available to the configured API account.

Use environment variables for model configuration so the model can be changed without modifying application code.

### 3.4 Database Grounding

The AI must retrieve actual results from MySQL.

Create a controlled set of reusable analytics tools, such as:

- get_market_summary()
- get_rent_trends()
- compare_neighbourhoods()
- analyse_property_characteristics()
- get_rent_distribution()
- get_mietenspiegel_benchmark()
- get_data_quality_report()

Each tool should:
1. Accept validated parameters.
2. Query approved analytics views or tables.
3. Return structured results.
4. Include sample counts and relevant date/source context.
5. Return errors clearly when data is unavailable.

Prefer predefined, parameterised SQL queries and approved database views over unrestricted model-generated SQL.

If a text-to-SQL capability is implemented, it must operate under strict validation and read-only permissions.

### 3.5 AI Response Quality

Every analytical answer should:
- Answer the user's question directly.
- Explain the relevant findings.
- Include actual numerical values where available.
- Include sample sizes when relevant.
- Explain important assumptions.
- Identify missing data and limitations.
- Distinguish historical listing observations from official benchmark data.

When appropriate, return:
- KPI cards.
- Tables.
- Bar charts.
- Line charts.
- Scatter plots.
- Distribution charts.

The AI should select a suitable visualisation based on the question and actual query results.

Do not generate a chart when the available data does not support it.

### 3.6 Dashboard and AI Integration

The AI should understand the currently selected dashboard filters.

For example, if the user selects:
- Neighbourhood: Altona.
- Snapshot: February 2020.
- Property type: Apartment.

And then asks:

"What is the median advertised rent per square metre?"

The AI should use those active filters when answering.

Provide a clear way for users to:
- Ask a question using active dashboard filters.
- Reset filters.
- Ask an independent question without dashboard filters.

The AI should not silently ignore active filters.

### 3.7 Dynamic Visualisation

When the AI returns analytical results, the application should be able to render the relevant visualisation inside the chat interface.

Examples:

User: Compare median rent across neighbourhoods.

AI:
- Explains the comparison.
- Returns the relevant neighbourhood values.
- Generates a bar chart.
- Displays the sample size for each neighbourhood.

User: Show the historical rent trend.

AI:
- Retrieves snapshot-level median rents.
- Explains the trend.
- Generates a line chart.

Charts must be rendered using Plotly or reusable Streamlit chart components, not generated as static AI images.

### 3.8 AI Safety and Cost Control

Implement these requirements:

- Use a dedicated read-only MySQL database account for the AI.
- Restrict database access to approved analytics views where practical.
- Never allow INSERT, UPDATE, DELETE, DROP, ALTER, CREATE or other write operations through the AI.
- Validate all tool arguments.
- Use parameterised SQL.
- Apply query timeouts and maximum row limits.
- Do not expose database credentials or API keys.
- Do not allow the model to execute arbitrary Python or shell commands.
- Never expose raw sensitive information unnecessarily.
- Handle API failures and database errors gracefully.
- Set reasonable token limits.
- Avoid sending entire datasets to the LLM.
- Send only relevant aggregated query results.
- Cache suitable repeated analytics queries.
- Display a useful message when API credits or rate limits are reached.

The application must support MOCK mode when an OpenAI API key is not configured. MOCK mode should allow development and dashboard testing without making API calls.

The API key must be stored only in the local `.env` file and must never be committed to Git or displayed in the UI.

### 3.9 AI Transparency

For analytical responses, provide a small expandable section called "Analysis Details" containing:
- Data source used.
- Filters applied.
- Date or snapshot context.
- Number of records analysed.
- Metric calculation used.

The AI must distinguish between:
- Verified database findings.
- Interpretations of those findings.
- General suggestions requiring further investigation.

Never invent data, citations, source information or market statistics.

---

## 4. Global Dashboard Requirements

Apply these requirements across the application:

- Professional SaaS-style interface.
- Consistent typography, spacing and colour palette.
- Sidebar navigation.
- Clear page titles and descriptions.
- Interactive charts and filters.
- Tooltips explaining business metrics.
- Loading states and useful error messages.
- Responsive layouts.
- Currency formatting in EUR.
- Rent per square metre displayed as €/m².
- Clear date and source labels.
- Consistent filter behaviour.
- Downloadable filtered tables where appropriate.

Build reusable components instead of duplicating code across pages.

---

## 5. Technical Implementation Requirements

Use the existing project stack where suitable:

- Python.
- MySQL.
- SQLAlchemy / PyMySQL.
- Pandas and NumPy.
- Streamlit.
- Plotly.
- OpenAI Python SDK.
- Pydantic.
- python-dotenv.
- Pytest.

Organise the application into separate modules for:
- Database connections.
- Data access and repositories.
- Analytics calculations.
- AI orchestration.
- AI tools.
- Dashboard pages.
- Shared visualisation components.
- Configuration.
- Testing.

Do not put the entire application into one Python file.

---

## 6. Testing and Acceptance Criteria

Before declaring the project complete, verify:

1. Every dashboard page loads successfully.
2. All KPI calculations are based on actual MySQL results.
3. Historical snapshot counts reconcile with the staging table.
4. Filters update the relevant charts and tables.
5. Benchmark comparisons use the correct benchmark characteristics.
6. Missing data and outliers are handled correctly.
7. The AI answers questions using database-backed results.
8. AI follow-up questions retain relevant context.
9. AI charts display actual returned query results.
10. Active dashboard filters are respected by the AI.
11. Invalid or unsafe database requests are rejected.
12. MOCK mode works without an API key.
13. API errors and database failures are handled gracefully.
14. No secrets are hardcoded.
15. The application can be launched using documented commands.

Provide a final project report describing:
- What was built.
- Application architecture.
- Dashboard pages.
- AI functionality.
- Database objects used.
- Tests executed and their results.
- Known limitations.
- How to run the complete application.

## FINAL EXPECTATION

Deliver a complete, working Hamburg Rental Market Intelligence application.

Do not stop after generating a project structure, mock dashboard, static charts or basic chatbot.

Implement the actual functionality, connect it to the existing MySQL database, test the application and fix implementation errors.

Work in phases, verify each phase before proceeding, and preserve the existing working data pipeline.