# Deployment – Streamlit Community Cloud (showcase edition)

The cloud copy cannot reach MySQL on a local PC, so it runs from a read-only data snapshot (`data/snapshot/letura_snapshot.sqlite`, 1.8 MB) exported from the finished MySQL database. Numbers are identical to the local version (verified: 3,759 listings, medians €12.94 / €13.20 / €13.52 / €13.89). Raw source tables are not included. The AI runs in demo (mock) mode: no API key is uploaded.

## Steps
1. (If data changed) `python scripts\run_pipeline.py` then `python scripts\export_snapshot.py`.
2. Create a **private** GitHub repository and upload the project. `.gitignore` already excludes `.env`, `.venv`, `logs/`.
   ```powershell
   cd C:\Letura_Intelligence
   git init
   git add .
   git status        # confirm .env and .venv are NOT listed
   git commit -m "Letura Intelligence showcase"
   git branch -M main
   git remote add origin https://github.com/<you>/letura-intelligence.git
   git push -u origin main
   ```
3. Go to https://share.streamlit.io → **New app** → pick the repo, branch `main`, main file `app/main.py`.
4. Under **Advanced settings → Secrets** paste:
   ```toml
   DATA_BACKEND = "snapshot"
   AI_ENABLED = "false"
   ```
5. Deploy. In app **Settings → Sharing**, choose who can view (invite by email, or public).

## Notes
- Do not add database credentials or an OpenAI key to the cloud secrets.
- To enable live AI later: add a **new** rotated `OPENAI_API_KEY` and `AI_ENABLED = "true"`; consider access restriction first because visitors would spend your credits.
- Free apps sleep after inactivity; the first visit may take ~30 seconds to wake.

# What to tell Letura (summary)

**Letura Intelligence – Hamburg Rental Market Analytics** is an end-to-end prototype: data engineering → database → analytics dashboard → AI analyst, built on 3,759 Hamburg listings (four snapshots, Sep 2018 – Feb 2020), the official Hamburg Mietenspiegel 2025 and the 2025 residential-location directory.

Things to know while viewing:
- The rents are **historical asking rents (2018–2020)**, not current prices. The Mietenspiegel (2025) is an official reference; the comparison is contextual, not a market premium or legal rent.
- It is a **showcase edition**: the viewer sees a bundled snapshot of the production database, and the AI analyst runs in demo mode. The full version runs on MySQL with a live OpenAI-powered analyst.
- Outliers are flagged, never deleted; small samples (<10 listings) are marked; missing values are shown, not filled.
- About a third of listings have no street address, so no residential-location class.
- Pages: Executive Overview, Market Explorer, Neighbourhoods, Property Insights, Mietenspiegel Benchmark, Data Quality & Pipeline, AI Analyst.
