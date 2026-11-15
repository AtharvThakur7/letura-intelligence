"""Deterministic MOCK analyst: keyword intent routing + templated, data-grounded explanations.

Used when no valid API key is configured, when AI_ENABLED=false, and as the
fallback when the OpenAI API is unavailable (rate limit / credits / network).
It calls the same tools as the live model, so every number comes from MySQL.
"""
from __future__ import annotations

import re

from letura.ai import tools as K
from letura.analytics import transforms as T

MONTHS = {"sep": "Sep 2018", "may": "May 2019", "oct": "Oct 2019", "feb": "Feb 2020"}
NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}
AMENITY_WORDS = {"balcony": "has_balcony", "balconies": "has_balcony", "garden": "has_garden", "lift": "has_lift", "elevator": "has_lift",
                 "kitchen": "has_kitchen", "cellar": "has_cellar", "new construction": "is_new_construction", "newly": "is_new_construction"}


def parse_snapshot(q: str) -> str | None:
    m = re.search(r"\b(sep(?:tember)?|may|oct(?:ober)?|feb(?:ruary)?)\.?\s*'?(2018|2019|2020|18|19|20)\b", q, re.I)
    if not m:
        return None
    label = MONTHS.get(m.group(1)[:3].lower())
    return label if label and label[-4:][-2:] == m.group(2)[-2:] else None


def parse_rooms(q: str) -> list[int]:
    out = []
    for m in re.finditer(r"\b(one|two|three|four|five|six|[1-6])[\s-]*(?:room|bed|zimmer)", q, re.I):
        out.append(NUMWORDS[m.group(1).lower()])
    return out


def find_neighbourhoods(q: str, names: list[str]) -> list[str]:
    qn = K._norm(q)
    hits = []
    for n in sorted(names, key=len, reverse=True):
        k = K._norm(n)
        if len(k) >= 4 and k in qn and not any(k in K._norm(h) for h in hits):
            hits.append(n)
    return hits


def route(question: str, memory: dict, names: list[str]) -> tuple[list[tuple[str, dict]], dict]:
    """Return ([(tool, args)], new_memory). Follow-ups reuse remembered neighbourhood/snapshot/dimension."""
    q = question.lower()
    mem = dict(memory)
    snap = parse_snapshot(q)
    nbh = find_neighbourhoods(question, names)
    rooms = parse_rooms(q)
    followup = bool(re.search(r"\b(and|what about|how about|same|that|those|them|it|there)\b", q)) and len(q.split()) < 12

    calls: list[tuple[str, dict]] = []
    scope: dict = {}
    if snap: scope["snapshot"] = snap
    if len(nbh) == 1 and not re.search(r"compare|versus|vs", q): scope["neighbourhood"] = nbh[0]

    if re.search(r"limitation|caveat|reliab|can we trust|how good is", q):
        calls = [("get_data_quality_report", {"topic": "overview"})]
    elif re.search(r"executive summary|key findings|summar", q):
        calls = [("get_market_summary", {}), ("get_rent_trends", {}), ("compare_neighbourhoods", {"top_n": 5}),
                 ("get_data_quality_report", {"topic": "overview"})]
    elif re.search(r"mietenspiegel|benchmark|reference rent|official", q):
        args: dict = {}
        y = re.search(r"\b(19\d{2}|20[0-2]\d)\b", q)
        if y:
            p = T.ms_construction_period(int(y.group(1)))
            if p: args["construction_period"] = p
        if re.search(r"\bgut|good", q): args["residential_location"] = "Gute Wohnlage"
        elif re.search(r"normal", q): args["residential_location"] = "Normale Wohnlage"
        if re.search(r"normal.*(good|gut)|(good|gut).*normal", q): args.pop("residential_location", None)
        a = re.search(r"(\d{2,3})\s*(?:m²|m2|sqm|square)", q)
        if a:
            args["living_area_category"] = {True: "bis unter 41", False: ""}[int(a.group(1)) < 41] or \
                ("41m² bis" if int(a.group(1)) < 66 else "66m² bis" if int(a.group(1)) < 91 else "ab 91")
        calls = [("get_mietenspiegel_benchmark", args)]
    elif re.search(r"missing|null|incomplete", q):
        calls = [("get_data_quality_report", {"topic": "missing_values"})]
    elif re.search(r"how many (records|listings).*(snapshot|each)|records.*each snapshot|available for each snapshot", q):
        calls = [("get_data_quality_report", {"topic": "snapshot_counts"})]
    elif re.search(r"suspicious|outlier|invalid|duplicate|data.quality|quality", q):
        calls = [("get_data_quality_report", {"topic": "outliers" if re.search(r"suspicious|outlier", q) else "overview"}),
                 ] + ([("get_rent_distribution", {})] if re.search(r"suspicious|outlier", q) else [])
    elif re.search(r"distribution|spread|histogram", q):
        calls = [("get_rent_distribution", dict(scope))]
    elif re.search(r"trend|over time|change[d]?\b|across the (available )?snapshots|historical", q) and not nbh:
        calls = [("get_rent_trends", {k: v for k, v in scope.items() if k != "snapshot"})]
    elif len(nbh) >= 2 or re.search(r"compare.*neighbourhood", q) and nbh:
        calls = [("compare_neighbourhoods", {"neighbourhoods": nbh, **({"snapshot": snap} if snap else {})})]
        mem["neighbourhoods"] = nbh
    elif re.search(r"normal.*(good|gut)|wohnlage|residential location|location class", q):
        calls = [("analyse_property_characteristics", {"dimension": "location_class", **({"snapshot": snap} if snap else {})})]
    elif any(w in q for w in AMENITY_WORDS):
        w = next(w for w in AMENITY_WORDS if w in q)
        calls = [("analyse_property_characteristics", {"dimension": AMENITY_WORDS[w], **scope})]
    elif re.search(r"larger|smaller|size|area|square", q) and not re.search(r"median.*per square", q):
        calls = [("analyse_property_characteristics", {"dimension": "size_band", **scope})]
    elif len(rooms) >= 2 or re.search(r"rooms?\b", q) and re.search(r"compare|differ|by", q):
        calls = [("analyse_property_characteristics", {"dimension": "room_band", **scope})]
    elif re.search(r"property type|type of|apartment type|types", q):
        calls = [("analyse_property_characteristics", {"dimension": "property_type", **scope})]
    elif re.search(r"construction|year built|building age|older|newer", q):
        calls = [("analyse_property_characteristics", {"dimension": "year_band", **scope})]
    elif re.search(r"factor|associated|drivers|higher (advertised )?rents", q):
        calls = [("analyse_property_characteristics", {"dimension": d}) for d in ["size_band", "year_band", "property_type", "has_balcony"]]
    elif re.search(r"investigate|further|neighbourhoods? should|focus", q):
        calls = [("compare_neighbourhoods", {"top_n": 8, "metric": "median"}), ("get_rent_distribution", {})]
    elif re.search(r"neighbourhood|district|bezirk|stadtteil|where|area.*(highest|cheapest|expensive)", q) or (re.search(r"highest|lowest|cheapest|most expensive|most listings", q)):
        metric = "count" if re.search(r"most (rental )?listings|listing volume|most listings", q) else "mean" if "average" in q or "mean" in q else "median"
        asc = bool(re.search(r"lowest|cheapest|least", q))
        calls = [("compare_neighbourhoods", {"metric": metric, "ascending": asc, "top_n": 10, **({"snapshot": snap} if snap else {})})]
    elif followup and mem.get("neighbourhoods") and nbh == []:
        calls = [("compare_neighbourhoods", {"neighbourhoods": mem["neighbourhoods"], **({"snapshot": snap} if snap else {})})]
    else:
        args = dict(scope)
        if len(rooms) == 1:
            args["rooms"] = str(rooms[0])
        if nbh and "neighbourhood" not in args: args["neighbourhood"] = nbh[0]
        calls = [("get_market_summary", args)]
    if len(rooms) == 1 and calls and calls[0][0] == "get_market_summary":
        calls[0][1].setdefault("rooms", str(rooms[0]))
    return calls, mem


def _fmt(v, d=2):
    return "n/a" if v is None else (f"{v:,.{d}f}" if isinstance(v, (int, float)) else str(v))


def explain(results: list[K.ToolResult]) -> str:
    """Templated Verified findings / Interpretation / Next steps from tool results only."""
    findings, interp, nxt = [], [], []
    for r in results:
        if not r.ok:
            findings.append(f"⚠ `{r.tool}`: {r.error}")
            continue
        s, rows = r.summary, r.rows
        if r.tool == "get_market_summary":
            findings.append(f"Across **{s['listings']:,} listings** ({r.filters_applied}), the median advertised cold rent is **€{_fmt(s['median_rent_per_sqm'])}/m²** "
                            f"(mean €{_fmt(s['mean_rent_per_sqm'])}; P25–P75 €{_fmt(s['p25'])}–€{_fmt(s['p75'])}). Median living area is {_fmt(s['median_living_space_sqm'], 1)} m² "
                            f"and median rooms {_fmt(s['median_rooms'], 1)}.")
            interp.append("The mean sits above the median, which indicates a right-skewed rent distribution driven by a premium tail.")
        elif r.tool == "get_rent_trends":
            for x in rows:
                findings.append(f"{x['snapshot']}: median **€{_fmt(x['median_rent_per_sqm'])}/m²** (n={x['listings']:,})")
            if s.get("change_pct_between_medians") is not None and s["first_snapshot"] != s["last_snapshot"]:
                interp.append(f"The median moved {s['change_pct_between_medians']:+.1f}% between {s['first_snapshot']} and {s['last_snapshot']}. "
                              "These are separate samples of listings, so this describes the advertised market mix, not like-for-like rent growth.")
        elif r.tool == "compare_neighbourhoods":
            metric = s["ranked_by"]
            key = {"median": "median_rent_per_sqm", "mean": "mean_rent_per_sqm", "count": "listings"}[metric]
            for x in rows[:10]:
                val = f"{int(x[key])} listings" if metric == "count" else f"€{_fmt(x[key])}/m²"
                findings.append(f"**{x['neighbourhood']}** – {val} (median €{_fmt(x['median_rent_per_sqm'])}, n={x['listings']})")
            interp.append("Rankings of neighbourhoods with small samples are volatile; see the sample-size column.")
        elif r.tool == "analyse_property_characteristics":
            for x in rows:
                findings.append(f"**{x['segment']}** – median €{_fmt(x['median_rent_per_sqm'])}/m² (n={x['listings']:,})")
            if "spearman_area_vs_rent_per_sqm" in s:
                findings.append(f"Spearman correlation between living area and rent/m²: **{s['spearman_area_vs_rent_per_sqm']:.2f}**.")
                interp.append("A negative value means larger apartments tend to have lower rent per m² in this dataset (association, not causation).")
            interp.append(f"Coverage for this characteristic is {s['coverage_pct']}% of listings in scope.")
        elif r.tool == "get_rent_distribution":
            findings.append(f"n={s['n']:,}; median €{_fmt(s['median'])}, P25–P75 €{_fmt(s['p25'])}–€{_fmt(s['p75'])}, P90 €{_fmt(s['p90'])}, P95 €{_fmt(s['p95'])}; range €{_fmt(s['min'])}–€{_fmt(s['max'])}/m².")
            findings.append(f"{s['iqr_outliers_flagged']} listings fall outside the 1.5×IQR fences (€{_fmt(s['iqr_fence_low'])}–€{_fmt(s['iqr_fence_high'])}); all are retained.")
            nxt.append("Review the highest rent/m² records on the Data Quality page to decide which are genuine premium listings.")
        elif r.tool == "get_mietenspiegel_benchmark":
            for x in rows[:8]:
                line = (f"{x['residential_location']}, {x['construction_period']}, {x['living_area_category']}: reference **€{_fmt(x['reference_rent_per_sqm'])}/m²** "
                        f"(range €{_fmt(x['minimum_rent_per_sqm'])}–€{_fmt(x['maximum_rent_per_sqm'])})")
                if x.get("hist_listing_count"):
                    line += f"; {x['hist_listing_count']} historical listings with median €{_fmt(x.get('hist_median_rent_sqm'))}/m²"
                findings.append(line)
            interp.append(K.BENCH)
        elif r.tool == "get_data_quality_report":
            sm = r.summary
            findings.append(f"{sm['checks_total']} automated checks: " + ", ".join(f"{sm.get('checks_'+k, 0)} {k}" for k in ["pass", "info", "warn", "fail"]) + ".")
            for x in rows[:8]:
                v = x["metric_pct"]
                findings.append(f"{x['check_name']}{' – ' + x['column_name'] if x.get('column_name') else ''}: {_fmt(x['metric_value'], 0)}" + (f" ({v:.1f}%)" if v is not None else "") + f" [{x['status']}]")
        elif r.tool == "run_readonly_sql":
            findings.append(f"Query returned {s['rows_returned']} rows.")
    for r in results:
        if r.ok:
            interp.extend(c for c in r.caveats[:2] if c not in interp)
    parts = ["**Verified database findings**\n" + "\n".join(f"- {f}" for f in findings)]
    if interp:
        parts.append("**Interpretation & caveats**\n" + "\n".join(f"- {i}" for i in dict.fromkeys(interp)))
    if nxt:
        parts.append("**Suggested follow-up (requires further investigation)**\n" + "\n".join(f"- {n}" for n in nxt))
    return "\n\n".join(parts)


LIMITATIONS = [
    "The listings are historical advertised cold rents from four independent snapshots (Sep 2018 – Feb 2020); they are not current 2026 rents and not signed contracts.",
    "Snapshots contain different properties, so changes in medians reflect the advertised mix as well as price movement.",
    "The Mietenspiegel 2025 is an official reference table (net cold rent, reference date 1 Apr 2025); the listings are asking rents from 2018–2020. "
    + K.BENCH,
    "Residential location classes (2025) are matched only where street, house-number range and odd/even numbering agree; 1,269 listings have no usable address.",
    "Outliers are flagged and kept; construction year is missing for 508 listings and heating costs for 2,050.",
    "Neighbourhood statistics with fewer than 10 listings are unreliable.",
]




def limitations_block() -> str:
    nl = chr(10)
    return "**Known limitations of this data**" + nl + nl.join(f"- {x}" for x in LIMITATIONS)
