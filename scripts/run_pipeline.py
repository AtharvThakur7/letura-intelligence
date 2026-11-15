"""Letura Intelligence – idempotent data pipeline.

Usage (from project root, with the virtual environment active):

    python scripts/run_pipeline.py                 # full build
    python scripts/run_pipeline.py --audit-only    # read-only audit, no writes
    python scripts/run_pipeline.py --dry-run       # compute everything in memory, write nothing
    python scripts/run_pipeline.py --skip-locations

Raw tables and the validated staging table are never modified.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from letura.config import LOG_DIR, REPORT_DIR, get_settings  # noqa: E402
from letura.db import admin_engine, table_exists  # noqa: E402
from letura.pipeline import build as B  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
(LOG_DIR / "pipeline").mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline" / f"pipeline_{RUN_ID}.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("pipeline")


class Step:
    def __init__(self, steps: list, name: str):
        self.steps, self.name = steps, name

    def __enter__(self):
        self.t0 = time.time()
        log.info("▶ %s", self.name)
        self.rec = {"step": self.name, "status": "running"}
        self.steps.append(self.rec)
        return self.rec

    def __exit__(self, exc_type, exc, tb):
        self.rec["seconds"] = round(time.time() - self.t0, 2)
        if exc:
            self.rec["status"] = "failed"
            self.rec["error"] = f"{exc_type.__name__}: {str(exc)[:400]}"
            log.error("✖ %s failed: %s", self.name, self.rec["error"])
            return False
        if self.rec["status"] == "running":
            self.rec["status"] = "ok"
        log.info("✔ %s (%ss) %s", self.name, self.rec["seconds"],
                 json.dumps({k: v for k, v in self.rec.items() if k not in {"step", "status", "seconds"}}, default=str)[:300])
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit-only", action="store_true", help="only connect and audit; no writes")
    ap.add_argument("--dry-run", action="store_true", help="compute transformations in memory; no writes")
    ap.add_argument("--skip-locations", action="store_true", help="skip optional Wohnlagen address matching")
    args = ap.parse_args()
    mode = "audit-only" if args.audit_only else "dry-run" if args.dry_run else "full"
    started = datetime.now().replace(microsecond=0)
    steps: list[dict] = []
    eng = admin_engine()
    status = "success"
    log.info("Letura Intelligence pipeline | run %s | mode=%s", RUN_ID, mode)

    try:
        with Step(steps, "1. Test database connection") as s:
            with eng.connect() as c:
                s["database"], s["mysql_version"] = c.execute(text("SELECT DATABASE(), VERSION()")).one()

        with Step(steps, "2-3. Audit source tables and verify counts") as s:
            counts = {}
            for t, exp in B.EXPECTED_SOURCE_COUNTS.items():
                n = int(pd.read_sql(text(f"SELECT COUNT(*) n FROM `{t}`"), eng).n[0]) if table_exists(t, eng) else None
                counts[t] = {"expected": exp, "actual": n, "ok": n == exp}
            s["counts"] = counts
            bad = [t for t, v in counts.items() if not v["ok"] and t != "fact_mietenspiegel_benchmarks"]
            if bad:
                raise RuntimeError(f"Source count mismatch for {bad} – stopping before any write")

        if args.audit_only:
            log.info("Audit-only mode: no database objects written.")
        else:
            with Step(steps, "4. Verify listing staging transformation") as s:
                v = pd.read_sql(text("""SELECT COUNT(*) n, SUM(baseRent IS NULL) mb, SUM(livingSpace IS NULL) ml,
                        SUM(rent_per_sqm IS NULL) mr, SUM(listing_date IS NULL) md FROM stg_hamburg_listings"""), eng).iloc[0]
                s.update({k: int(v[k]) for k in v.index})
                if int(v.n) != 3759 or int(v.mb) or int(v.ml) or int(v.mr) or int(v.md):
                    raise RuntimeError("stg_hamburg_listings failed validation")

            with Step(steps, "5. Verify / build Mietenspiegel fact table") as s:
                if args.dry_run:
                    s["action"] = "dry-run (verify only)"
                    s["rows"] = int(pd.read_sql(text("SELECT COUNT(*) n FROM fact_mietenspiegel_benchmarks"), eng).n[0])
                else:
                    s.update(B.build_fact_mietenspiegel_if_missing(eng))

            with Step(steps, "6. Build enriched listings (+ optional location matching)") as s:
                if args.dry_run:
                    stg = pd.read_sql(text("SELECT " + ", ".join(f"`{c}`" for c in B.STG_COLUMNS) + " FROM stg_hamburg_listings"), eng)
                    locs = None if args.skip_locations else pd.read_sql(text(
                        "SELECT location_id, street, house_number_start, house_number_end, numbering_type, location_class, location_score FROM raw_residential_locations"), eng)
                    df = B.enrich_listings(stg, locs)
                    s.update({"rows": len(df), "location_status": df["location_match_status"].value_counts().to_dict(), "written": False})
                else:
                    s.update(B.build_int_listings(eng, run_location_matching=not args.skip_locations))

            if not args.dry_run:
                lst = pd.read_sql(text("SELECT * FROM int_hamburg_listings"), eng)
                fact = pd.read_sql(text("SELECT * FROM fact_mietenspiegel_benchmarks"), eng)
                with Step(steps, "7. Build analytics tables") as s:
                    s["analytics_hamburg_rental_market"] = B.swap_in(B.analytics_rental_market(lst), "analytics_hamburg_rental_market", eng)
                    s["analytics_hamburg_neighbourhoods"] = B.swap_in(B.analytics_neighbourhoods(lst), "analytics_hamburg_neighbourhoods", eng)
                    s["analytics_hamburg_property_insights"] = B.swap_in(B.analytics_property_insights(lst), "analytics_hamburg_property_insights", eng)
                    s["analytics_mietenspiegel_reference"] = B.swap_in(B.analytics_mietenspiegel_reference(fact, lst), "analytics_mietenspiegel_reference", eng)
                    s["analytics_location_matching"] = B.swap_in(B.analytics_location_matching(lst), "analytics_location_matching", eng)

                with Step(steps, "8. Run data quality checks") as s:
                    dq = B.analytics_data_quality(eng, lst, fact)
                    s["rows"] = B.swap_in(dq, "analytics_data_quality", eng)
                    s["status_counts"] = dq["status"].value_counts().to_dict()
                    fails = dq[dq.status == "fail"]
                    if len(fails):
                        s["status"] = "warning"
                        s["failed_checks"] = fails["check_name"].tolist()

                with Step(steps, "8b. Create AI view and read-only account grants") as s:
                    st = get_settings()
                    s.update(B.build_ai_view_and_grants(eng, st.ai.readonly_user, st.ai.readonly_password.get_secret_value(), st.db.name))

                with Step(steps, "9. Generate reports") as s:
                    s["files"] = write_reports(eng, dq, steps)
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        log.exception("Pipeline stopped: %s", exc)

    if any(s.get("status") == "warning" for s in steps) and status == "success":
        status = "warning"
    finished = datetime.now().replace(microsecond=0)
    if mode == "full":
        try:
            B.log_pipeline_run(eng, {"run_id": RUN_ID, "started_at": started, "finished_at": finished, "mode": mode,
                                     "status": status, "steps": steps, "message": f"log file {LOG_FILE.name}"})
        except Exception as exc:  # noqa: BLE001
            log.error("Could not record pipeline run: %s", exc)
    (LOG_DIR / "pipeline" / "last_run.json").write_text(json.dumps(
        {"run_id": RUN_ID, "mode": mode, "status": status, "started_at": started, "finished_at": finished, "steps": steps},
        default=str, indent=2), encoding="utf-8")
    log.info("Pipeline finished: %s (%s)", status.upper(), LOG_FILE)
    return 0 if status in {"success", "warning"} else 1


def write_reports(eng, dq: pd.DataFrame, steps: list) -> list[str]:
    files = []
    market = pd.read_sql(text("SELECT * FROM analytics_hamburg_rental_market ORDER BY snapshot_order"), eng)
    loc = pd.read_sql(text("SELECT * FROM analytics_location_matching WHERE snapshot='All snapshots'"), eng)
    lines = [f"# Data Quality Report", "", f"Generated by pipeline run `{RUN_ID}` at {datetime.now():%Y-%m-%d %H:%M}.", "",
             "Outliers and suspicious values are **flagged, never removed**. All 3,759 Hamburg records are retained.", "",
             "## Check summary", "", "| Status | Checks |", "|---|---:|"]
    for k, v in dq["status"].value_counts().items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## All checks", "", "| # | Category | Check | Object | Column | Value | % | Expected | Status | Details |",
              "|---:|---|---|---|---|---:|---:|---:|---|---|"]
    for r in dq.itertuples():
        fmt = lambda x: "" if x is None or (isinstance(x, float) and x != x) else (f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}")
        lines.append(f"| {r.check_id} | {r.category} | {r.check_name} | {r.object_name} | {r.column_name or ''} | "
                     f"{fmt(r.metric_value)} | {fmt(r.metric_pct)} | {fmt(r.expected_value)} | {r.status} | {r.details} |")
    lines += ["", "## Snapshot market summary (historical asking rents, €/m² cold)", "",
              "| Snapshot | Listings | Median | Mean | P25 | P75 | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in market.itertuples():
        lines.append(f"| {r.snapshot} | {r.listing_count:,} | {r.rent_sqm_median:.2f} | {r.rent_sqm_mean:.2f} | {r.rent_sqm_p25:.2f} | "
                     f"{r.rent_sqm_p75:.2f} | {r.rent_sqm_min:.2f} | {r.rent_sqm_max:.2f} |")
    lines += ["", "## Wohnlagen address matching", "", "| Status | Listings | Share |", "|---|---:|---:|"]
    for r in loc.itertuples():
        lines.append(f"| {r.match_status} | {r.listing_count:,} | {r.share_pct:.1f}% |")
    p = REPORT_DIR / "data_quality_report.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    files.append(str(p.relative_to(ROOT)))
    dq.to_csv(REPORT_DIR / "data_quality_checks.csv", index=False, encoding="utf-8")
    files.append("reports/data_quality_checks.csv")
    return files


if __name__ == "__main__":
    raise SystemExit(main())
