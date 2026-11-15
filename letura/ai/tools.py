"""Controlled analytics tools exposed to the AI analyst.

Every tool:
* validates its arguments (Pydantic);
* reads only approved MySQL objects (via the read-only engine);
* returns a structured ``ToolResult`` with sample counts, filters, date/source
  context and caveats;
* returns ``ok=False`` with a clear message when data is unavailable.

No tool executes model-generated code. ``run_readonly_sql`` is the only
free-form tool and is guarded by ``sqlguard`` + a SELECT-only DB account.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator

from letura.analytics import repo, stats, transforms as T
from letura.analytics.filters import AMENITIES, FilterState, apply_filters
from letura.db import read_df
from letura.ai import sqlguard

HIST = ("Historical advertised cold rents from ImmoScout24 snapshots (Sep 2018, May 2019, Oct 2019, Feb 2020); "
        "independent snapshots, not current 2026 rents.")
BENCH = ("These datasets differ in reference period, population and methodology. This comparison is contextual, "
         "not a same-period market premium or legal rent determination.")
SNAPS = Literal["Sep 2018", "May 2019", "Oct 2019", "Feb 2020"]
DIMENSIONS = ["size_band", "room_band", "year_band", "property_type", "has_balcony", "has_garden", "has_lift",
              "has_kitchen", "is_new_construction", "has_cellar", "bezirk", "location_class"]


# ----------------------------------------------------------------- result container
class ChartSpec(BaseModel):
    kind: Literal["bar", "hbar", "line", "scatter", "hist", "box"]
    x: str
    y: Optional[str] = None
    color: Optional[str] = None
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    order: Optional[list[str]] = None


class ToolResult(BaseModel):
    tool: str
    ok: bool = True
    title: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)       # headline numbers
    rows: list[dict[str, Any]] = Field(default_factory=list)     # table rows (aggregates only)
    chart: Optional[ChartSpec] = None
    n_records: int = 0
    source: str = ""
    filters_applied: str = ""
    period: str = ""
    calculation: str = ""
    caveats: list[str] = Field(default_factory=list)
    error: str = ""

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)

    def for_llm(self, max_rows: int = 40) -> dict:
        d = self.model_dump(exclude={"chart"})
        d["rows"] = self.rows[:max_rows]
        if len(self.rows) > max_rows:
            d["rows_truncated"] = f"{len(self.rows) - max_rows} more rows not shown"
        return d


def _clean(v):
    if isinstance(v, float):
        return None if v != v else round(v, 3)
    if hasattr(v, "item"):
        try:
            return _clean(v.item())
        except Exception:  # noqa: BLE001
            return str(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    return v


def records(df: pd.DataFrame, limit: int = 200) -> list[dict]:
    return [{k: _clean(v) for k, v in r.items()} for r in df.head(limit).to_dict("records")]


def fail(tool: str, msg: str) -> ToolResult:
    return ToolResult(tool=tool, ok=False, error=msg, caveats=[msg])


# ----------------------------------------------------------------- shared context
class Context:
    """Per-request context: listings provider + the dashboard filters in force."""

    def __init__(self, filters: FilterState | None = None, listings: Callable[[], pd.DataFrame] | None = None):
        self.filters = filters or FilterState()
        self._listings = listings or repo.load_listings
        self.notes: list[str] = []

    def df(self, overrides: dict | None = None) -> tuple[pd.DataFrame, str]:
        """Dashboard filters + explicit question-level overrides (the question wins; stated in the output)."""
        f = FilterState(**{k: (list(v) if isinstance(v, list) else v) for k, v in self.filters.to_dict().items()})
        used = []
        for key, val in (overrides or {}).items():
            if not val:
                continue
            if getattr(f, key) and getattr(f, key) != val:
                self.notes.append(f"The question names {key.replace('_', ' ')} = {val}, which overrides the dashboard filter {getattr(f, key)}.")
            setattr(f, key, val)
            used.append(key)
        return apply_filters(self._listings(), f), f.describe()


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def resolve_neighbourhoods(names: list[str] | None, all_names: list[str]) -> tuple[list[str], list[str]]:
    lookup = {_norm(n): n for n in all_names}
    found, missing = [], []
    for n in names or []:
        k = _norm(n)
        hit = lookup.get(k) or next((v for kk, v in lookup.items() if k and (kk.startswith(k) and len(k) >= 4)), None)
        (found if hit else missing).append(hit or n)
    return found, missing


def _ctx_fields(ctx: Context, df: pd.DataFrame, fdesc: str) -> dict:
    snaps = sorted({str(s) for s in df["snapshot"].dropna().unique()}, key=lambda s: T.SNAPSHOT_ORDER.index(s) if s in T.SNAPSHOT_ORDER else 9)
    return dict(source="MySQL table int_hamburg_listings (via read-only account)", n_records=len(df),
                filters_applied=fdesc + ("" if not ctx.notes else " | " + " ".join(ctx.notes)),
                period=", ".join(snaps) if snaps else "no data")


# ----------------------------------------------------------------- argument models
class _Base(BaseModel):
    model_config = {"extra": "forbid"}
    use_dashboard_filters: bool = True


class MarketSummaryArgs(_Base):
    snapshot: Optional[SNAPS] = None
    neighbourhood: Optional[str] = None
    property_type: Optional[str] = None
    rooms: Optional[str] = Field(default=None, description="Room band: 1, 1.5–2, 2.5–3, 3.5–4, 4.5+ (or a number such as 2).")
    amenity: Optional[Literal[tuple(AMENITIES)]] = None


class RentTrendArgs(_Base):
    neighbourhood: Optional[str] = None
    property_type: Optional[str] = None
    rooms: Optional[str] = None


class CompareNbhArgs(_Base):
    neighbourhoods: Optional[list[str]] = Field(default=None, max_length=10)
    snapshot: Optional[SNAPS] = None
    metric: Literal["median", "mean", "count"] = "median"
    top_n: int = Field(default=10, ge=1, le=30)
    min_listings: int = Field(default=10, ge=1, le=100)
    ascending: bool = False


class PropertyArgs(_Base):
    dimension: Literal[tuple(DIMENSIONS)]
    snapshot: Optional[SNAPS] = None
    neighbourhood: Optional[str] = None


class DistributionArgs(_Base):
    snapshot: Optional[SNAPS] = None
    neighbourhood: Optional[str] = None
    bins: int = Field(default=12, ge=4, le=30)


class BenchmarkArgs(_Base):
    construction_period: Optional[str] = None
    residential_location: Optional[Literal["Normale Wohnlage", "Gute Wohnlage"]] = None
    living_area_category: Optional[str] = None
    compare_with_listings: bool = True


class QualityArgs(_Base):
    topic: Literal["overview", "missing_values", "outliers", "snapshot_counts", "duplicates", "reconciliation", "locations"] = "overview"


class SQLArgs(BaseModel):
    model_config = {"extra": "forbid"}
    sql: str = Field(max_length=sqlguard.MAX_LENGTH)
    purpose: str = Field(default="", max_length=300)


def _room_band(v: str | None) -> list[str] | None:
    if not v:
        return None
    if v in T.ROOM_BAND_ORDER:
        return [v]
    try:
        b = T.room_band(float(str(v).replace(",", ".")))
        return [b] if b else None
    except ValueError:
        return None


def _overrides(ctx: Context, a: _Base, df_all: pd.DataFrame, **kw) -> tuple[dict, list[str]]:
    missing: list[str] = []
    ov: dict = {}
    if kw.get("snapshot"):
        ov["snapshots"] = [kw["snapshot"]]
    if kw.get("neighbourhood"):
        found, miss = resolve_neighbourhoods([kw["neighbourhood"]], sorted(df_all["neighbourhood"].dropna().unique()))
        ov["neighbourhoods"], missing = found, miss
    if kw.get("property_type"):
        ov["property_types"] = [kw["property_type"]]
    if kw.get("rooms"):
        ov["rooms"] = _room_band(kw["rooms"])
    if kw.get("amenity"):
        ov["amenities"] = [kw["amenity"]]
    return ov, missing


def _scoped(ctx: Context, a: _Base, **kw) -> tuple[pd.DataFrame, str, list[str]]:
    all_df = ctx._listings()
    ov, missing = _overrides(ctx, a, all_df, **kw)
    if not a.use_dashboard_filters:
        saved = ctx.filters
        ctx.filters = FilterState()
        try:
            df, fdesc = ctx.df(ov)
        finally:
            ctx.filters = saved
        fdesc = fdesc.replace("No filters (all 3,759 Hamburg listings)", "No dashboard filters (independent question)")
    else:
        df, fdesc = ctx.df(ov)
    return df, fdesc, missing


# ----------------------------------------------------------------- tools
def get_market_summary(ctx: Context, a: MarketSummaryArgs) -> ToolResult:
    df, fdesc, missing = _scoped(ctx, a, snapshot=a.snapshot, neighbourhood=a.neighbourhood, property_type=a.property_type,
                                 rooms=a.rooms, amenity=a.amenity)
    if missing:
        return fail("get_market_summary", f"Neighbourhood not found in the data: {', '.join(missing)}.")
    if df.empty:
        return fail("get_market_summary", "No listings match the filters.")
    d = stats.describe(df["rent_per_sqm"])
    ls, rm = stats.describe(df["livingSpace"]), stats.describe(df["noRooms"])
    summ = {"listings": d["n"], "median_rent_per_sqm": d["median"], "mean_rent_per_sqm": d["mean"], "p25": d["p25"], "p75": d["p75"],
            "p90": d["p90"], "min": d["min"], "max": d["max"], "median_living_space_sqm": ls["median"], "median_rooms": rm["median"],
            "median_base_rent_eur": float(df["baseRent"].median()), "neighbourhoods": int(df["neighbourhood"].nunique())}
    cav = [HIST] + (["Small sample (n<10): treat as indicative."] if d["n"] < 10 else [])
    return ToolResult(tool="get_market_summary", title="Market summary", summary=summ, rows=records(pd.DataFrame([summ])),
                      calculation="rent_per_sqm = baseRent ÷ livingSpace; percentiles by linear interpolation.",
                      caveats=cav + ctx.notes, **_ctx_fields(ctx, df, fdesc))


def get_rent_trends(ctx: Context, a: RentTrendArgs) -> ToolResult:
    df, fdesc, missing = _scoped(ctx, a, neighbourhood=a.neighbourhood, property_type=a.property_type, rooms=a.rooms)
    if missing:
        return fail("get_rent_trends", f"Neighbourhood not found: {', '.join(missing)}.")
    if df.empty:
        return fail("get_rent_trends", "No listings match the filters.")
    g = stats.grouped_describe(df.assign(snapshot=df["snapshot"].astype(str)), "snapshot")
    g["o"] = g["snapshot"].map(T.SNAPSHOT_ORDER.index)
    g = g.sort_values("o")
    out = g[["snapshot", "n", "median", "mean", "p25", "p75", "sample_flag"]].rename(columns={"n": "listings", "median": "median_rent_per_sqm", "mean": "mean_rent_per_sqm"})
    first, last = out.iloc[0], out.iloc[-1]
    chg = None if first["median_rent_per_sqm"] in (None, 0) else (last["median_rent_per_sqm"] / first["median_rent_per_sqm"] - 1) * 100
    summ = {"first_snapshot": first["snapshot"], "last_snapshot": last["snapshot"], "first_median": first["median_rent_per_sqm"],
            "last_median": last["median_rent_per_sqm"], "change_pct_between_medians": None if chg is None else round(chg, 1)}
    cav = [HIST, "Snapshots are different samples of listings; a change in medians is not a like-for-like price change."]
    if (out["listings"] < 10).any():
        cav.append("Some snapshots have fewer than 10 listings under these filters.")
    return ToolResult(tool="get_rent_trends", title="Median advertised rent per m² by snapshot", summary=summ, rows=records(out),
                      chart=ChartSpec(kind="line", x="snapshot", y="median_rent_per_sqm", title="Median advertised rent (€/m²) by snapshot",
                                      ylabel="€/m²", order=T.SNAPSHOT_ORDER),
                      calculation="Median of baseRent ÷ livingSpace within each snapshot.", caveats=cav + ctx.notes, **_ctx_fields(ctx, df, fdesc))


def compare_neighbourhoods(ctx: Context, a: CompareNbhArgs) -> ToolResult:
    # Scope = dashboard filters (if used) minus any neighbourhood filter when the question names neighbourhoods.
    base = FilterState(**{k: (list(v) if isinstance(v, list) else v) for k, v in ctx.filters.to_dict().items()}) if a.use_dashboard_filters else FilterState()
    if a.neighbourhoods and base.neighbourhoods:
        ctx.notes.append("Dashboard neighbourhood filter ignored because the question names specific neighbourhoods.")
        base.neighbourhoods = []
    if a.snapshot:
        if base.snapshots and base.snapshots != [a.snapshot]:
            ctx.notes.append(f"Question names snapshot {a.snapshot}, overriding the dashboard snapshot filter.")
        base.snapshots = [a.snapshot]
    pool_df = apply_filters(ctx._listings(), base)
    fdesc = base.describe() if (a.use_dashboard_filters or a.snapshot) else "No dashboard filters (independent question)"
    if pool_df.empty:
        return fail("compare_neighbourhoods", "No listings match the filters.")
    g = stats.grouped_describe(pool_df, "neighbourhood")
    g = g.rename(columns={"n": "listings", "median": "median_rent_per_sqm", "mean": "mean_rent_per_sqm"})
    notes = []
    if a.neighbourhoods:
        found, miss = resolve_neighbourhoods(a.neighbourhoods, sorted(pool_df["neighbourhood"].dropna().unique()))
        if miss:
            notes.append(f"No listings found for: {', '.join(miss)} (under the current scope).")
        g = g[g["neighbourhood"].isin(found)]
        if g.empty:
            return fail("compare_neighbourhoods", "None of the named neighbourhoods have listings in this scope. " + " ".join(notes))
    else:
        g = g[g["listings"] >= a.min_listings]
        if g.empty:
            return fail("compare_neighbourhoods", f"No neighbourhood has at least {a.min_listings} listings in this scope.")
    key = {"median": "median_rent_per_sqm", "mean": "mean_rent_per_sqm", "count": "listings"}[a.metric]
    g = g.sort_values(key, ascending=a.ascending).head(a.top_n if not a.neighbourhoods else 30)
    out = g[["neighbourhood", "listings", "median_rent_per_sqm", "mean_rent_per_sqm", "p25", "p75", "min", "max", "sample_flag"]]
    small = out[out["listings"] < stats.SMALL_SAMPLE_THRESHOLD]
    cav = [HIST] + notes + ([f"Small samples (n<10): {', '.join(small['neighbourhood'])}."] if len(small) else []) + ctx.notes
    top = out.iloc[0]
    summ = {"ranked_by": a.metric, "top_neighbourhood": top["neighbourhood"], "top_value": top[key], "neighbourhoods_returned": len(out)}
    return ToolResult(tool="compare_neighbourhoods", title="Neighbourhood comparison", summary=summ, rows=records(out),
                      chart=ChartSpec(kind="hbar", x="neighbourhood", y=key, title=f"{a.metric.title()} by neighbourhood",
                                      ylabel="Listings" if a.metric == "count" else "€/m²"),
                      calculation=f"Per neighbourhood: {a.metric} of baseRent ÷ livingSpace" + (f"; neighbourhoods with < {a.min_listings} listings excluded." if not a.neighbourhoods else "."),
                      caveats=cav, **_ctx_fields(ctx, pool_df, fdesc))


def analyse_property_characteristics(ctx: Context, a: PropertyArgs) -> ToolResult:
    df, fdesc, missing = _scoped(ctx, a, snapshot=a.snapshot, neighbourhood=a.neighbourhood)
    if missing:
        return fail("analyse_property_characteristics", f"Neighbourhood not found: {', '.join(missing)}.")
    if df.empty:
        return fail("analyse_property_characteristics", "No listings match the filters.")
    dim = a.dimension
    seg = df[dim].map(lambda v: "Missing / unknown" if v is None or (isinstance(v, float) and v != v) else ("Yes" if v is True else "No" if v is False else str(v)))
    g = stats.grouped_describe(df.assign(segment=seg), "segment").rename(columns={"n": "listings", "median": "median_rent_per_sqm", "mean": "mean_rent_per_sqm"})
    order = {"size_band": T.SIZE_BAND_ORDER, "room_band": T.ROOM_BAND_ORDER, "year_band": T.YEAR_BAND_ORDER}.get(dim)
    if order:
        g["o"] = g["segment"].map(lambda s: order.index(s) if s in order else 99)
        g = g.sort_values("o")
    out = g[["segment", "listings", "median_rent_per_sqm", "mean_rent_per_sqm", "p25", "p75", "sample_flag"]]
    cov = round(100 * df[dim].notna().mean(), 1)
    sub = df.dropna(subset=["livingSpace", "rent_per_sqm"])
    extra = {}
    if dim == "size_band" and len(sub) > 10:
        extra["spearman_area_vs_rent_per_sqm"] = round(stats.spearman(sub["livingSpace"], sub["rent_per_sqm"]), 3)
    cav = [HIST, f"Coverage: {cov}% of listings have a value for this characteristic.",
           "Differences are associations; characteristics correlate with each other (size, age, location), so they are not causal effects."]
    if dim == "location_class":
        cav.append("Location class is available only for listings whose address matched the 2025 Wohnlagenverzeichnis.")
    return ToolResult(tool="analyse_property_characteristics", title=f"Rent per m² by {dim}", summary={"dimension": dim, "coverage_pct": cov, **extra},
                      rows=records(out), chart=ChartSpec(kind="bar", x="segment", y="median_rent_per_sqm", title=f"Median rent per m² by {dim.replace('_', ' ')}",
                                                         ylabel="€/m²", order=order),
                      calculation="Median/mean/P25/P75 of baseRent ÷ livingSpace per segment; rows with missing values grouped as 'Missing / unknown'.",
                      caveats=cav + ctx.notes, **_ctx_fields(ctx, df, fdesc))


def get_rent_distribution(ctx: Context, a: DistributionArgs) -> ToolResult:
    df, fdesc, missing = _scoped(ctx, a, snapshot=a.snapshot, neighbourhood=a.neighbourhood)
    if missing:
        return fail("get_rent_distribution", f"Neighbourhood not found: {', '.join(missing)}.")
    s = df["rent_per_sqm"].dropna()
    if s.empty:
        return fail("get_rent_distribution", "No listings match the filters.")
    d = stats.describe(s)
    cut = pd.cut(s, bins=a.bins)
    h = cut.value_counts(sort=False).reset_index()
    h.columns = ["bin", "listings"]
    h["bin"] = h["bin"].map(lambda i: f"{i.left:.1f}–{i.right:.1f}")
    lo, hi = stats.iqr_bounds(s)
    n_out = int(((s < lo) | (s > hi)).sum())
    summ = {**{k: d[k] for k in ["n", "median", "mean", "p25", "p75", "p90", "p95", "iqr", "min", "max"]}, "iqr_fence_low": lo, "iqr_fence_high": hi, "iqr_outliers_flagged": n_out}
    return ToolResult(tool="get_rent_distribution", title="Rent per m² distribution", summary=summ, rows=records(h),
                      chart=ChartSpec(kind="bar", x="bin", y="listings", title="Distribution of advertised rent per m²", xlabel="€/m² bin", ylabel="Listings"),
                      calculation=f"Equal-width histogram with {a.bins} bins; outliers by 1.5×IQR fences (flagged, retained).",
                      caveats=[HIST, f"{n_out} listings lie outside the IQR fences (€{lo:.2f}–€{hi:.2f}); they are retained."] + ctx.notes, **_ctx_fields(ctx, df.loc[s.index], fdesc))


def resolve_ms_period(text: str, periods: list[str]) -> str | None:
    """Accept '1994 bis 2010', '1994-2010', '1994 to 2010', or a single year such as 1985."""
    s = str(text).strip()
    if s in periods:
        return s
    years = [int(y) for y in re.findall(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)", s)]
    if len(years) >= 2:
        for p in periods:
            if [int(y) for y in re.findall(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)", p)] == years[:2]:
                return p
    if len(years) == 1:
        return T.ms_construction_period(years[0])
    hits = [p for p in periods if s.lower() in p.lower()]
    return hits[0] if len(hits) == 1 else None


def resolve_ms_area(text: str, areas: list[str]) -> str | None:
    s = str(text).strip().lower().replace("m2", "m²").replace("sqm", "m²")
    exact = [x for x in areas if x.lower() == s]
    if exact:
        return exact[0]
    nums = re.findall(r"\d+", s)
    if nums:
        n = int(nums[0])
        if any(w in s for w in ("under", "unter", "below", "<", "less")):
            hits = [x for x in areas if x.lower().startswith(f"bis unter {n}")]
        elif "ab" in s or "+" in s or "over" in s or "more" in s:
            hits = [x for x in areas if x.lower().startswith(f"ab {n}")]
        else:
            hits = [x for x in areas if x.lower().startswith(f"{n}m²") or x.lower().startswith(f"bis unter {n}")]
        if len(hits) == 1:
            return hits[0]
    hits = [x for x in areas if s in x.lower()]
    return hits[0] if len(hits) == 1 else None


def get_mietenspiegel_benchmark(ctx: Context, a: BenchmarkArgs) -> ToolResult:
    try:
        ref = repo.load_table("analytics_mietenspiegel_reference")
    except Exception as exc:  # noqa: BLE001
        return fail("get_mietenspiegel_benchmark", f"Benchmark table unavailable: {str(exc)[:150]}")
    m = ref
    periods = sorted(ref.construction_period.unique(), key=lambda p: T.MS_PERIODS.index(p) if p in T.MS_PERIODS else 99)
    areas = sorted(ref.living_area_category.unique(), key=lambda p: T.MS_AREA_ORDER.index(p) if p in T.MS_AREA_ORDER else 99)
    hint = f" Valid construction periods: {', '.join(periods)}. Valid living-area categories: {', '.join(areas)}."
    if a.construction_period:
        period = resolve_ms_period(a.construction_period, periods)
        if period is None:
            return fail("get_mietenspiegel_benchmark", f"Could not match construction period '{a.construction_period}'.{hint}")
        m = m[m.construction_period == period]
    if a.residential_location:
        m = m[m.residential_location == a.residential_location]
    if a.living_area_category:
        area = resolve_ms_area(a.living_area_category, areas)
        if area is None:
            return fail("get_mietenspiegel_benchmark", f"Could not match living-area category '{a.living_area_category}'.{hint}")
        m = m[m.living_area_category == area]
    if m.empty:
        return fail("get_mietenspiegel_benchmark", "The Mietenspiegel publishes no cell for this exact combination (some cells are not published); no value is estimated." + hint)
    cols = ["construction_period", "residential_location", "living_area_category", "reference_rent_per_sqm", "minimum_rent_per_sqm", "maximum_rent_per_sqm"]
    if a.compare_with_listings:
        cols += ["hist_listing_count", "hist_median_rent_sqm"]
    out = m[cols].head(60)
    r0 = m.iloc[0]
    summ = {"cells_returned": len(m), "reference_date": str(pd.to_datetime(r0.reference_date).date()), "publisher": r0.publisher,
            "median_reference_rent": float(m.reference_rent_per_sqm.median()), "lowest_min": float(m.minimum_rent_per_sqm.min()),
            "highest_max": float(m.maximum_rent_per_sqm.max())}
    return ToolResult(tool="get_mietenspiegel_benchmark", title="Hamburg Mietenspiegel 2025 reference rents", summary=summ, rows=records(out),
                      chart=ChartSpec(kind="bar", x="construction_period", y="reference_rent_per_sqm", title="Official reference rent (€/m²)", ylabel="€/m²",
                                      color="residential_location" if m.residential_location.nunique() > 1 else None, order=T.MS_PERIODS) if m.construction_period.nunique() > 1 else None,
                      n_records=len(m), source="MySQL view analytics_mietenspiegel_reference (official Hamburg Mietenspiegel 2025, ref. date 2025-04-01)",
                      filters_applied=", ".join(f"{k}={v}" for k, v in a.model_dump(exclude={"use_dashboard_filters", "compare_with_listings"}).items() if v) or "none",
                      period="Reference date 1 April 2025 (official); historical listings 2018–2020",
                      calculation="Official published Mittelwert, Spanne min/max (net cold rent excl. heating and operating costs). hist_* columns = 2018–20 listings mapped to the same characteristics.",
                      caveats=[BENCH, "Reference rents are official benchmarks, not advertised rents."])


def get_data_quality_report(ctx: Context, a: QualityArgs) -> ToolResult:
    try:
        dq = repo.load_table("analytics_data_quality")
    except Exception as exc:  # noqa: BLE001
        return fail("get_data_quality_report", f"Quality table unavailable: {str(exc)[:150]}")
    cat = {"missing_values": ["missing_values"], "outliers": ["outliers", "suspicious_values"], "duplicates": ["duplicates"],
           "reconciliation": ["reconciliation", "row_counts"], "locations": ["locations"], "snapshot_counts": ["reconciliation"]}.get(a.topic)
    d = dq if cat is None else dq[dq.category.isin(cat)]
    if a.topic == "snapshot_counts":
        d = d[d.check_name.str.startswith("snapshot_count")]
    if a.topic == "missing_values":
        d = d.sort_values("metric_pct", ascending=False)
    out = d[["category", "check_name", "column_name", "metric_value", "metric_pct", "expected_value", "status", "details"]]
    counts = dq["status"].value_counts().to_dict()
    summ = {"checks_total": len(dq), **{f"checks_{k}": int(v) for k, v in counts.items()}, "rows_returned": len(out)}
    chart = None
    if a.topic == "missing_values":
        chart = ChartSpec(kind="hbar", x="column_name", y="metric_pct", title="Missing values (% of listings)", ylabel="% missing")
    if a.topic == "snapshot_counts":
        chart = ChartSpec(kind="bar", x="check_name", y="metric_value", title="Records per snapshot", ylabel="Listings")
    return ToolResult(tool="get_data_quality_report", title=f"Data quality – {a.topic.replace('_', ' ')}", summary=summ, rows=records(out, 60), chart=chart,
                      n_records=len(out), source="MySQL table analytics_data_quality (written by the pipeline)",
                      filters_applied="not filtered (quality checks always cover all 3,759 Hamburg records)", period="Whole dataset, Sep 2018 – Feb 2020",
                      calculation="Pipeline checks: reconciliation to raw, NA-token missingness, duplicates, rule-based flags and 1.5×IQR outlier flags.",
                      caveats=["Outliers and suspicious records are flagged, never deleted."])


def run_readonly_sql(ctx: Context, a: SQLArgs) -> ToolResult:
    """Free-form fallback. Heavily guarded; prefer the dedicated tools."""
    try:
        safe = sqlguard.validate_select(a.sql)
    except sqlguard.UnsafeSQL as exc:
        return fail("run_readonly_sql", f"Query rejected: {exc}")
    try:
        df = read_df(safe)
    except Exception as exc:  # noqa: BLE001
        return fail("run_readonly_sql", f"Query failed: {str(exc)[:200]}")
    return ToolResult(tool="run_readonly_sql", title="Custom read-only query", rows=records(df, sqlguard.MAX_ROWS), n_records=len(df),
                      summary={"rows_returned": len(df), "purpose": a.purpose}, source="MySQL approved analytics views (SELECT-only account, READ ONLY session)",
                      filters_applied="SQL as validated: " + safe, period="see query", calculation="Executed exactly as shown in filters_applied.",
                      caveats=["Result of a model-proposed query; dashboard filters are NOT applied automatically to custom SQL."])


# ----------------------------------------------------------------- registry
TOOLS: dict[str, tuple[type[BaseModel], Callable[[Context, Any], ToolResult], str]] = {
    "get_market_summary": (MarketSummaryArgs, get_market_summary, "Headline stats (listings, median/mean/P25/P75 rent per m², median area/rooms) for the scope; optional snapshot/neighbourhood/type/rooms/amenity."),
    "get_rent_trends": (RentTrendArgs, get_rent_trends, "Median/mean rent per m² for each of the four snapshots (line chart)."),
    "compare_neighbourhoods": (CompareNbhArgs, compare_neighbourhoods, "Rank or compare neighbourhoods by median/mean rent or listing count; pass `neighbourhoods` to compare specific ones."),
    "analyse_property_characteristics": (PropertyArgs, analyse_property_characteristics, "Rent per m² by one characteristic: size_band, room_band, year_band, property_type, has_balcony/garden/lift/kitchen/cellar, is_new_construction, bezirk, location_class."),
    "get_rent_distribution": (DistributionArgs, get_rent_distribution, "Histogram + percentile stats + outlier fences of rent per m²."),
    "get_mietenspiegel_benchmark": (BenchmarkArgs, get_mietenspiegel_benchmark, "Official Hamburg Mietenspiegel 2025 reference rent/range for characteristics, optionally with matched historical listings."),
    "get_data_quality_report": (QualityArgs, get_data_quality_report, "Data quality results: overview, missing_values, outliers, snapshot_counts, duplicates, reconciliation, locations."),
    "run_readonly_sql": (SQLArgs, run_readonly_sql, "LAST RESORT: a single SELECT on approved views (analytics_*, v_ai_listings, fact_mietenspiegel_benchmarks). Only when no other tool fits."),
}


def openai_tool_specs() -> list[dict]:
    specs = []
    for name, (model, _fn, desc) in TOOLS.items():
        schema = model.model_json_schema()
        schema.pop("title", None)
        schema["additionalProperties"] = False
        if name != "run_readonly_sql":
            schema["properties"].pop("use_dashboard_filters", None)
        specs.append({"type": "function", "function": {"name": name, "description": desc, "parameters": schema}})
    return specs


def execute_tool(name: str, raw_args: dict | str | None, ctx: Context, use_filters: bool = True) -> ToolResult:
    """Validate arguments and run a tool. Never raises."""
    import json
    if name not in TOOLS:
        return fail(name, f"Unknown tool '{name}'.")
    model, fn, _ = TOOLS[name]
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else (raw_args or {})
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        if "use_dashboard_filters" in model.model_fields:
            args["use_dashboard_filters"] = use_filters
        parsed = model(**args)
    except (ValidationError, ValueError) as exc:
        return fail(name, f"Invalid arguments: {str(exc)[:250]}")
    try:
        return fn(ctx, parsed)
    except Exception as exc:  # noqa: BLE001
        return fail(name, f"Tool failed: {type(exc).__name__}: {str(exc)[:200]}")
