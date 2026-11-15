"""Export the finished analytics data from MySQL into a bundled read-only SQLite file.

Used for cloud demos (Streamlit Community Cloud) where MySQL on your PC is unreachable.
Raw source tables are NOT exported. Run after `python scripts/run_pipeline.py`:

    python scripts/export_snapshot.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from letura.db import SNAPSHOT_PATH, admin_engine  # noqa: E402
from letura.pipeline.build import AI_VIEW_SQL  # noqa: E402

TABLES = ["int_hamburg_listings", "fact_mietenspiegel_benchmarks", "analytics_hamburg_rental_market",
          "analytics_hamburg_neighbourhoods", "analytics_hamburg_property_insights", "analytics_mietenspiegel_reference",
          "analytics_data_quality", "analytics_location_matching", "meta_pipeline_runs"]
DROP_COLUMNS = {"int_hamburg_listings": ["regio1", "regio2", "street", "streetPlain"]}  # keep payload lean / no raw text


def main() -> None:
    eng = admin_engine()
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.unlink()
    con = sqlite3.connect(SNAPSHOT_PATH)
    for t in TABLES:
        df = pd.read_sql(f"SELECT * FROM `{t}`", eng)
        df = df.drop(columns=[c for c in DROP_COLUMNS.get(t, []) if c in df.columns])
        for c in df.columns:
            if df[c].dtype == object:
                try:
                    df[c] = pd.to_numeric(df[c]) if t == "int_hamburg_listings" and c in {"heatingCosts"} else df[c]
                except Exception:  # noqa: BLE001
                    pass
            if str(df[c].dtype).startswith("datetime") or (df[c].dtype == object and df[c].map(lambda v: hasattr(v, "isoformat")).any()):
                df[c] = df[c].map(lambda v: v.isoformat() if hasattr(v, "isoformat") else v)
            if df[c].dtype == object and df[c].map(lambda v: v.__class__.__name__ == "Decimal").any():
                df[c] = df[c].astype(float)
        df.to_sql(t, con, index=False, if_exists="replace")
        print(f"{t:42} {len(df):>6} rows")
    view = AI_VIEW_SQL.replace("CREATE OR REPLACE SQL SECURITY DEFINER VIEW", "CREATE VIEW")
    con.execute(view)
    con.commit()
    con.execute("VACUUM")
    con.close()
    print(f"\nSnapshot written: {SNAPSHOT_PATH} ({SNAPSHOT_PATH.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
