"""Unit tests – no database required."""
from datetime import date

import pandas as pd
import pytest

from letura.ai import sqlguard, tools as K
from letura.ai.analyst import Analyst
from letura.analytics import stats, transforms as T
from letura.analytics.filters import FilterState, apply_filters
from letura.config import AISettings
from letura.ui.components import csv_bytes


# ---------------------------------------------------------------- transformations
@pytest.mark.parametrize("raw,expected", [("Sep18", date(2018, 9, 1)), ("May19", date(2019, 5, 1)), ("Oct19", date(2019, 10, 1)),
                                           ("Feb20", date(2020, 2, 1)), ("NA", None), ("", None), ("Xyz19", None), ("2019-05", None)])
def test_snapshot_date_parsing(raw, expected):
    assert T.parse_snapshot_date(raw) == expected


def test_rent_per_sqm_calculation():
    assert T.rent_per_sqm(1000, 80) == 12.5
    assert T.rent_per_sqm("999.00", "78.00") == 12.81
    assert T.rent_per_sqm(1000, 0) is None
    assert T.rent_per_sqm("NA", 50) is None
    assert T.rent_per_sqm(1000, None) is None


@pytest.mark.parametrize("v", ["NA", "", " na ", None, float("nan"), "no_information", "N/A"])
def test_missing_tokens(v):
    assert T.is_missing(v)
    assert T.to_number(v) is None


def test_non_missing_tokens():
    assert not T.is_missing("0") and T.to_number("0") == 0.0
    assert T.to_bool("TRUE") is True and T.to_bool("FALSE") is False and T.to_bool("NA") is None


def test_construction_period_mapping_edges():
    assert T.ms_construction_period(1918) == "bis 31.12.1918"
    assert T.ms_construction_period(1919) == "01.01.1919 bis 20.06.1948"
    assert T.ms_construction_period(1948) is None          # boundary falls mid-year: not guessed
    assert T.ms_construction_period(1949) == "21.06.1948 bis 31.12.1960"
    assert T.ms_construction_period(2024) == "2021 bis 2024"
    assert T.ms_construction_period(1111) is None and T.ms_construction_period(None) is None


def test_area_category_depends_on_location():
    assert T.ms_area_category(100, "normal") == "ab 91m²"
    assert T.ms_area_category(100, "gut") == "91m² bis unter 131m²"
    assert T.ms_area_category(140, "gut") == "ab 131m²"
    assert T.ms_area_category(100, None) is None             # not guessed without a location class
    assert T.ms_area_category(50, None) == "41m² bis unter 66m²"


def test_neighbourhood_names_and_bezirk():
    assert T.neighbourhood_name("Altona_Nord") == "Altona-Nord"
    assert T.neighbourhood_name("St._Pauli") == "St. Pauli"
    assert T.bezirk_for("Horn") == "Hamburg-Mitte" and T.bezirk_for("Eppendorf") == "Hamburg-Nord"


# ---------------------------------------------------------------- location matching
def _locs():
    return pd.DataFrame([
        dict(location_id=1, street="Hafenstraße", house_number_start="001", house_number_end="015", numbering_type="U", location_class="normal", location_score=346.0),
        dict(location_id=2, street="Hafenstraße", house_number_start="002", house_number_end="014", numbering_type="G", location_class="gut", location_score=500.0),
        dict(location_id=3, street="Aalkrautweg", house_number_start="001", house_number_end="035a", numbering_type="U", location_class="gut", location_score=590.0),
        dict(location_id=4, street="Sonderweg", house_number_start="001", house_number_end="020", numbering_type="S", location_class="normal", location_score=400.0),
        dict(location_id=5, street="Zweideutig", house_number_start="001", house_number_end="010", numbering_type="S", location_class="normal", location_score=400.0),
        dict(location_id=6, street="Zweideutig", house_number_start="005", house_number_end="015", numbering_type="S", location_class="gut", location_score=500.0),
    ])


def test_street_key_handles_entities_and_unicode():
    assert T.street_key("Horner Landstra&szlig;e") == T.street_key("Horner Landstr.") == T.street_key("Horner Landstrasse")
    assert T.decode_street("B&ouml;melburgweg") == "Bömelburgweg"


def test_location_matching_rules():
    idx = T.LocationIndex(_locs())
    assert idx.match("Hafenstra&szlig;e", "7").location_class == "normal"      # odd
    assert idx.match("Hafenstraße", "8").location_class == "gut"               # even
    assert idx.match("Hafenstraße", "16").status == "unmatched_number"          # out of range
    assert idx.match("Aalkrautweg", "9a").status == "matched"                  # suffix handled
    assert idx.match("Aalkrautweg", "36").status == "unmatched_number"
    assert idx.match("Sonderweg", "4").status == "matched"                     # S = any parity
    assert idx.match("Nirgendwo", "4").status == "unmatched_street"
    assert idx.match("Hafenstraße", "NA").status == "no_address"
    assert idx.match("Zweideutig", "7").status == "ambiguous"                  # conflicting classes: never forced
    assert idx.match("Zweideutig", "7").location_class is None


# ---------------------------------------------------------------- statistics / outliers
def test_describe_percentiles_and_empty():
    d = stats.describe([1, 2, 3, 4, 100])
    assert d["n"] == 5 and d["median"] == 3 and d["p25"] == 2 and d["p75"] == 4 and d["max"] == 100
    e = stats.describe([])
    assert e["n"] == 0 and e["median"] is None
    assert stats.describe([1, None, "NA", 3])["n"] == 2


def test_outliers_are_flagged_not_removed():
    s = pd.Series([10, 11, 12, 11, 10, 12, 11, 300.0, None])
    flags = stats.flag_outliers(s)
    assert len(flags) == len(s)                      # nothing dropped
    assert flags.iloc[7] == "high" and flags.iloc[8] is None and flags.iloc[0] == "normal"


def test_spearman_without_scipy():
    x = pd.Series([1, 2, 3, 4, 5]); y = pd.Series([10, 8, 6, 4, 2])
    assert stats.spearman(x, y) == pytest.approx(-1.0)


def test_sample_flags():
    assert stats.sample_flag(3) == "very_small" and stats.sample_flag(7) == "small" and stats.sample_flag(10) == "ok"


# ---------------------------------------------------------------- dashboard filters
def test_filters_and_outlier_preservation(listings):
    assert len(apply_filters(listings, FilterState())) == len(listings)
    out = apply_filters(listings, FilterState(snapshots=["Feb 2020"], neighbourhoods=["Eppendorf"]))
    assert len(out) == 3 and set(out["neighbourhood"]) == {"Eppendorf"}
    assert (out["baseRent"] == 99999).any()           # extreme record still present
    assert len(apply_filters(listings, FilterState(area_range=(70, 80)))) == 6
    assert len(apply_filters(listings, FilterState(amenities=["has_balcony"]))) == int(listings["has_balcony"].sum())
    assert apply_filters(listings, FilterState(neighbourhoods=["Nowhere"])).empty


def test_filter_does_not_mutate_source(listings):
    n = len(listings)
    apply_filters(listings, FilterState(snapshots=["Sep 2018"]))
    assert len(listings) == n


def test_csv_export_roundtrip(listings):
    sub = apply_filters(listings, FilterState(neighbourhoods=["Horn"]))
    back = pd.read_csv(pd.io.common.BytesIO(csv_bytes(sub)))
    assert len(back) == len(sub) and list(back.columns) == list(sub.columns)


# ---------------------------------------------------------------- SQL safety
@pytest.mark.parametrize("sql", [
    "DROP TABLE analytics_data_quality", "DELETE FROM analytics_data_quality", "UPDATE analytics_data_quality SET status='x'",
    "INSERT INTO analytics_data_quality VALUES (1)", "CREATE TABLE t (a int)", "ALTER TABLE v_ai_listings ADD x INT",
    "TRUNCATE analytics_data_quality", "SELECT * FROM raw_rental_listings", "SELECT * FROM stg_hamburg_listings",
    "SELECT * FROM mysql.user", "SELECT * FROM information_schema.tables", "SELECT 1; DROP TABLE x",
    "SELECT * FROM v_ai_listings -- comment", "SELECT * FROM v_ai_listings /* x */", "SELECT SLEEP(10) FROM v_ai_listings",
    "SELECT * FROM v_ai_listings INTO OUTFILE 'c:/x.txt'", "SELECT * FROM v_ai_listings UNION SELECT * FROM v_ai_listings",
    "SELECT LOAD_FILE('c:/x') FROM v_ai_listings", "SELECT * FROM analytics_data_quality WHERE 1=1 FOR UPDATE",
    "WITH a AS (SELECT 1) SELECT * FROM a", "SET GLOBAL x=1", "SHOW TABLES", "GRANT ALL ON *.* TO x", "", "   ",
    "SELECT * FROM `raw_rental_listings`", "SELECT @@version FROM v_ai_listings", "CALL p()", "SELECT * FROM letura_intelligence.v_ai_listings",
    "SELECT * FROM v_ai_listings LIMIT 5 OFFSET 2",
])
def test_unsafe_sql_rejected(sql):
    with pytest.raises(sqlguard.UnsafeSQL):
        sqlguard.validate_select(sql)


def test_safe_sql_accepted_and_limited():
    out = sqlguard.validate_select("SELECT snapshot, AVG(rent_per_sqm) FROM v_ai_listings GROUP BY snapshot")
    assert out.endswith(f"LIMIT {sqlguard.MAX_ROWS}")
    assert sqlguard.validate_select("select * from analytics_hamburg_rental_market limit 5;").endswith("limit 5")
    assert sqlguard.validate_select("SELECT * FROM v_ai_listings LIMIT 100000").endswith(f"LIMIT {sqlguard.MAX_ROWS}")
    assert "'DROP TABLE'" in sqlguard.validate_select("SELECT * FROM v_ai_listings WHERE neighbourhood = 'DROP TABLE'")


def test_sql_tool_rejects_unsafe_without_touching_db():
    r = K.execute_tool("run_readonly_sql", {"sql": "DELETE FROM v_ai_listings"}, K.Context())
    assert not r.ok and "rejected" in r.error.lower()


def test_tool_argument_validation():
    ctx = K.Context(listings=lambda: pd.DataFrame())
    assert not K.execute_tool("nonexistent_tool", {}, ctx).ok
    assert not K.execute_tool("get_market_summary", {"snapshot": "Jan 2030"}, ctx).ok
    assert not K.execute_tool("get_market_summary", {"evil": "x"}, ctx).ok
    assert not K.execute_tool("analyse_property_characteristics", {"dimension": "password"}, ctx).ok
    assert not K.execute_tool("compare_neighbourhoods", {"top_n": 9999}, ctx).ok
    assert not K.execute_tool("get_market_summary", "{not json", ctx).ok


# ---------------------------------------------------------------- tools on fixture
def test_tools_use_filters_and_report_context(listings):
    ctx = K.Context(FilterState(snapshots=["Feb 2020"]), lambda: listings)
    r = K.execute_tool("get_market_summary", {}, ctx, use_filters=True)
    assert r.ok and r.n_records == 5 and "Feb 2020" in r.filters_applied and r.summary["listings"] == 5
    r2 = K.execute_tool("get_market_summary", {}, ctx, use_filters=False)
    assert r2.n_records == 10 and "independent" in r2.filters_applied.lower()


def test_compare_named_neighbourhoods_ignores_dashboard_nbh_filter(listings):
    ctx = K.Context(FilterState(neighbourhoods=["Horn"]), lambda: listings)
    r = K.execute_tool("compare_neighbourhoods", {"neighbourhoods": ["Horn", "Eppendorf"]}, ctx)
    assert r.ok and {x["neighbourhood"] for x in r.rows} == {"Horn", "Eppendorf"}
    assert any("ignored" in c for c in r.caveats) or "ignored" in r.filters_applied


def test_unknown_neighbourhood_is_clear_error(listings):
    r = K.execute_tool("get_market_summary", {"neighbourhood": "Atlantis"}, K.Context(listings=lambda: listings))
    assert not r.ok and "Atlantis" in r.error


def test_trends_have_chart_spec_and_counts(listings):
    r = K.execute_tool("get_rent_trends", {}, K.Context(listings=lambda: listings))
    assert r.ok and r.chart.kind == "line" and [x["snapshot"] for x in r.rows] == ["Sep 2018", "Feb 2020"]
    assert all(x["listings"] == 5 for x in r.rows)


# ---------------------------------------------------------------- AI mock mode
def test_mock_mode_without_api_key(listings):
    a = Analyst(AISettings(enabled=True, api_key=""), listings=lambda: listings)
    assert a.mode == "mock" and "MOCK" in a.status_text()
    assert Analyst(AISettings(enabled=False, api_key="sk-realistic-looking-key-123456789"), listings=lambda: listings).mode == "mock"
    r = a.answer("What is the median rent per square metre?", [], FilterState(), True)
    assert r.mode == "mock" and r.results and r.results[0].ok and "Verified database findings" in r.text


def test_mock_respects_filters_and_independent_mode(listings):
    a = Analyst(AISettings(enabled=False), listings=lambda: listings)
    f = FilterState(snapshots=["Feb 2020"], neighbourhoods=["Horn"])
    assert a.answer("What is the median rent per square metre?", [], f, True).results[0].n_records == 2
    assert a.answer("What is the median rent per square metre?", [], f, False).results[0].n_records == 10


def test_mock_follow_up_keeps_context(listings):
    a = Analyst(AISettings(enabled=False), listings=lambda: listings)
    h = [{"role": "user", "content": "Compare Horn and Eppendorf"}, {"role": "assistant", "content": "...", "memory": {"neighbourhoods": ["Horn", "Eppendorf"]}}]
    r = a.answer("And in Sep 2018?", h)
    assert r.tool_calls[0]["name"] == "compare_neighbourhoods" and r.tool_calls[0]["args"]["snapshot"] == "Sep 2018"


class _Boom:
    class chat:
        class completions:
            @staticmethod
            def create(**kw):
                raise RuntimeError("insufficient_quota: You exceeded your current quota")


def test_api_failure_falls_back_gracefully(listings):
    a = Analyst(AISettings(enabled=True, api_key="sk-test-key-123456789"), client=_Boom, listings=lambda: listings)
    r = a.answer("What is the median rent per square metre?", [], FilterState(), True)
    assert r.mode == "mock-fallback" and "credits" in r.notice.lower() and r.results


def test_secrets_not_in_repr():
    s = AISettings(api_key="sk-secret-value-abcdefghijk")
    assert "secret-value" not in repr(s) and "secret-value" not in str(s.model_dump())
