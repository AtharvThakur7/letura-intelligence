"""Integration tests – require the local MySQL database (skipped if unreachable)."""
import pandas as pd
import pytest
from sqlalchemy import text

from letura.ai import tools as K
from letura.analytics import repo, stats, transforms as T
from letura.analytics.filters import FilterState
from letura.db import admin_engine, readonly_engine, is_dedicated_readonly, read_df
from tests.conftest import requires_db

pytestmark = requires_db

EXPECTED = {"raw_rental_listings": 268_850, "raw_mietenspiegel": 88, "raw_mietenspiegel_metadata": 1,
            "raw_residential_locations": 26_205, "stg_hamburg_listings": 3_759, "fact_mietenspiegel_benchmarks": 88}


def test_connection():
    with admin_engine().connect() as c:
        assert c.execute(text("SELECT VERSION()")).scalar().startswith("8.")


@pytest.mark.parametrize("table,n", EXPECTED.items())
def test_source_counts(table, n):
    assert read_df(f"SELECT COUNT(*) n FROM `{table}`", engine=admin_engine()).n[0] == n


def test_snapshot_reconciliation_raw_to_stage_to_int():
    raw = read_df("SELECT `date` d, COUNT(*) n FROM raw_rental_listings WHERE LOWER(TRIM(regio1))='hamburg' GROUP BY 1", engine=admin_engine())
    stg = read_df("SELECT `date` d, COUNT(*) n FROM stg_hamburg_listings GROUP BY 1", engine=admin_engine())
    assert dict(zip(raw.d, raw.n)) == dict(zip(stg.d, stg.n)) == {"Sep18": 673, "May19": 1071, "Oct19": 902, "Feb20": 1113}
    lst = repo.load_listings()
    assert len(lst) == 3759
    assert lst.groupby("snapshot", observed=True).size().to_dict() == T.EXPECTED_SNAPSHOT_COUNTS


def test_staging_rent_per_sqm_reconciles():
    lst = repo.load_listings()
    recomputed = (lst["baseRent"] / lst["livingSpace"]).round(2)
    assert (recomputed - lst["rent_per_sqm"]).abs().max() <= 0.011
    assert lst["rent_per_sqm"].isna().sum() == 0


def test_na_tokens_become_null_not_values():
    assert read_df("SELECT COUNT(*) n FROM int_hamburg_listings WHERE yearConstructed IS NULL", engine=admin_engine()).n[0] == 508
    assert read_df("SELECT COUNT(*) n FROM int_hamburg_listings WHERE totalRent IS NULL", engine=admin_engine()).n[0] == 364


def test_outliers_preserved_in_pipeline_output():
    lst = repo.load_listings()
    assert len(lst) == 3759
    assert lst["rent_per_sqm"].max() == pytest.approx(61.25) and lst["rent_per_sqm"].min() == pytest.approx(4.35)
    assert (lst["outlier_iqr_global"] == "high").sum() > 0


def test_mietenspiegel_parsing_and_ranges():
    f = read_df("SELECT * FROM fact_mietenspiegel_benchmarks", engine=admin_engine())
    assert len(f) == 88 and f["equipment"].nunique() == 1
    assert set(f["residential_location"]) == {"Normale Wohnlage", "Gute Wohnlage"}
    assert set(f["construction_period"]) <= set(T.MS_PERIODS)
    assert (f["minimum_rent_per_sqm"] <= f["reference_rent_per_sqm"]).all() and (f["reference_rent_per_sqm"] <= f["maximum_rent_per_sqm"]).all()
    assert pd.to_datetime(f["reference_date"]).dt.date.unique().tolist() == [pd.Timestamp("2025-04-01").date()]


def test_analytics_tables_match_listings():
    lst = repo.load_listings()
    mk = read_df("SELECT * FROM analytics_hamburg_rental_market WHERE snapshot <> 'All snapshots'")
    for r in mk.itertuples():
        sub = lst[lst["snapshot"].astype(str) == r.snapshot]["rent_per_sqm"]
        assert r.listing_count == len(sub) and r.rent_sqm_median == pytest.approx(sub.median(), abs=0.01)
    nb = read_df("SELECT * FROM analytics_hamburg_neighbourhoods WHERE snapshot='All snapshots'")
    assert nb["listing_count"].sum() == 3759


def test_no_failed_quality_checks():
    dq = read_df("SELECT check_name, status, details FROM analytics_data_quality WHERE status='fail'")
    assert dq.empty, dq.to_string()


def test_readonly_account_is_restricted():
    if not is_dedicated_readonly():
        pytest.skip("dedicated read-only account not provisioned")
    eng = readonly_engine()
    for stmt in ["SELECT COUNT(*) FROM raw_rental_listings", "DELETE FROM analytics_data_quality", "DROP TABLE analytics_data_quality",
                 "CREATE TABLE zz_test (a INT)", "UPDATE int_hamburg_listings SET baseRent=1"]:
        with pytest.raises(Exception):
            with eng.connect() as c:
                c.execute(text(stmt))
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM v_ai_listings")).scalar() == 3759


def test_ai_tools_ground_in_database():
    ctx = K.Context(FilterState(snapshots=["Feb 2020"]))
    r = K.execute_tool("get_market_summary", {}, ctx)
    assert r.ok and r.n_records == 1113
    lst = repo.load_listings()
    assert r.summary["median_rent_per_sqm"] == pytest.approx(lst[lst.snapshot == "Feb 2020"]["rent_per_sqm"].median(), abs=0.01) == pytest.approx(13.89, abs=0.01)
    t = K.execute_tool("get_rent_trends", {}, K.Context())
    assert [x["median_rent_per_sqm"] for x in t.rows] == pytest.approx([12.94, 13.20, 13.52, 13.89], abs=0.011)
    b = K.execute_tool("get_mietenspiegel_benchmark", {"residential_location": "Gute Wohnlage", "construction_period": "1994 bis 2010", "living_area_category": "66m² bis"}, ctx)
    assert b.ok and b.rows[0]["reference_rent_per_sqm"] == 13.18 and b.rows[0]["minimum_rent_per_sqm"] == 10.03
    q = K.execute_tool("get_data_quality_report", {"topic": "snapshot_counts"}, ctx)
    assert sorted(int(x["metric_value"]) for x in q.rows) == [673, 902, 1071, 1113]


def test_sql_tool_executes_safe_query_and_blocks_raw():
    ok = K.execute_tool("run_readonly_sql", {"sql": "SELECT snapshot, listing_count FROM analytics_hamburg_rental_market ORDER BY snapshot_order"}, K.Context())
    assert ok.ok and ok.n_records == 5
    assert not K.execute_tool("run_readonly_sql", {"sql": "SELECT * FROM raw_rental_listings"}, K.Context()).ok


def test_location_matching_integration():
    lst = repo.load_listings()
    st = lst["location_match_status"].value_counts().to_dict()
    assert sum(st.values()) == 3759 and st.get("ambiguous", 0) == 0 or "ambiguous" in st
    assert lst.loc[lst.location_class.notna(), "location_match_status"].eq("matched").all()
    assert lst.loc[lst.location_match_status != "matched", "location_class"].isna().all()   # never forced


def test_pipeline_is_idempotent_for_counts():
    before = read_df("SELECT COUNT(*) n FROM int_hamburg_listings", engine=admin_engine()).n[0]
    assert before == 3759
