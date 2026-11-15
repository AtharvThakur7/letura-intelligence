# Data Dictionary

## Source and staging tables (unchanged)
| Table | Rows | Notes |
|---|---:|---|
| raw_rental_listings | 268,850 | all columns text; literal `NA` tokens |
| raw_mietenspiegel / _metadata | 88 / 1 | official 2025 reference rents |
| raw_residential_locations | 26,205 | PDF states 25,786 (+419 preserved) |
| stg_hamburg_listings | 3,759 | Hamburg only; typed numerics; `listing_date`, `rent_per_sqm` |
| fact_mietenspiegel_benchmarks | 88 | parsed characteristics, reference date, publisher |

## int_hamburg_listings (3,759 rows, key `source_record_id`)
| Column | Meaning |
|---|---|
| snapshot | Sep 2018 / May 2019 / Oct 2019 / Feb 2020 |
| neighbourhood, bezirk | Stadtteil (`regio3`, underscores → spaces/hyphens); administrative Bezirk |
| baseRent, totalRent, serviceCharge, heatingCosts | EUR; `NA` → NULL |
| livingSpace, noRooms | m², rooms |
| rent_per_sqm | baseRent ÷ livingSpace (advertised **cold** rent, €/m²) |
| rent_per_sqm_check | independent recomputation used for reconciliation |
| size_band, room_band, year_band | analytical bands |
| property_type | `typeOfFlat`; NULL if `NA` |
| has_balcony/garden/lift/kitchen/cellar, is_new_construction | booleans from TRUE/FALSE |
| outlier_iqr_global / _snapshot | `normal`/`high`/`low` by 1.5×IQR – **flag only** |
| quality_flags | comma list: rent_sqm_below_5, rent_sqm_above_40, living_space_below_15, implausible_construction_year, total_rent_below_base_rent, area_per_room_below_8 |
| is_flagged | any flag or outlier |
| location_match_status | matched / ambiguous / unmatched_street / unmatched_number / no_address |
| location_class, location_score | Wohnlagenverzeichnis 2025 class (normal/gut) – only when matched |
| ms_construction_period, ms_residential_location, ms_living_area_category | Mietenspiegel characteristic mapping (NULL when not reliably mappable, e.g. year 1948) |

## Analytics tables
| Table | Grain |
|---|---|
| analytics_hamburg_rental_market | snapshot (+ "All snapshots"): count, median/mean/P25/P75/P90/P95/IQR/min/max rent/m², median base rent, area, rooms, outlier counts |
| analytics_hamburg_neighbourhoods | snapshot × neighbourhood: count, rent stats, median area/rooms/base rent, location share, `sample_flag`, rank (n ≥ 10 only) |
| analytics_hamburg_property_insights | snapshot × dimension × segment, with coverage % and sample flag |
| analytics_mietenspiegel_reference | one row per official cell + range check + matched historical listing stats + caveat text |
| analytics_location_matching | snapshot × match status |
| analytics_data_quality | one row per automated check (category, metric, expected, status pass/info/warn/fail) |
| meta_pipeline_runs | one row per full pipeline run with step JSON |
| v_ai_listings | SELECT-only view of listing-level fields used for AI SQL |

## Mietenspiegel characteristics
Construction period (10 classes), equipment (single class: *mit Bad und Sammelheizung*), residential location (Normale/Gute Wohnlage), living-area category (6 labels; "Gute Wohnlage" splits ≥91 m² into 91–131 and ≥131). 88 of 90 possible cells are published (the two absent cells, both Gute Wohnlage, are "bis unter 41m²" × 2021–2024 and "ab 131m²" × 1961–1967; they are shown as "not published" and never estimated).
