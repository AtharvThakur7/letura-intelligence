# Data Sources and Limitations

## Sources
1. **German rental listings (`immo_data.csv`)** – ImmoScout24 advertised rents, 268,850 rows; Hamburg subset 3,759 across four independent snapshots (Sep 2018: 673; May 2019: 1,071; Oct 2019: 902; Feb 2020: 1,113).
2. **Hamburg Mietenspiegel 2025** – official reference rents (net cold rent excl. heating and operating costs), reference date 1 April 2025, publisher Behörde für Stadtentwicklung und Wohnen (Amt für Wohnen, Stadterneuerung und Bodenordnung).
3. **Hamburg Wohnlagenverzeichnis 2025** – street / house-number-range residential location classes (normal, gut) extracted from PDF.

## Limitations
- Historical **asking** rents, **not** current 2026 rents and not signed contracts. Never labelled as current.
- Snapshots are independent samples; median changes mix price movement with a changing mix of listings.
- Asking cold rent ≠ Mietenspiegel reference rent. Comparisons are contextual only: *"These datasets differ in reference period, population and methodology. This comparison is contextual, not a same-period market premium or legal rent determination."*
- Wohnlage classes are 2025 classifications applied to 2018–2020 listings. Matching is conservative (street key + number range + odd/even; S = any). Result: 2,422 matched (64.4%), 1,269 no usable address (33.8%), 41 street not found, 27 number out of range, 0 ambiguous. Unmatched listings get **no** class.
- Location extract has 26,205 rows vs 25,786 stated (+419). All rows preserved; cause not determined.
- Missing: construction year 508 (13.5%), total rent 364, service charge 91, heating costs 2,050 (54.5%); several secondary fields >40% missing. Values are never imputed.
- 183 listings (4.9%) exceed the 1.5×IQR upper fence; 16 other rule-based flags. All retained.
- Only 3 historical listings fall in the *selected default* Mietenspiegel cell for Gute Wohnlage 1994–2010 (<41 m²); comparisons with n<5 are refused.
- No coordinates in the source → no map.
- Neighbourhoods with <10 listings are flagged; rankings exclude them by default.
- Possible re-listings: 33 same-snapshot and 21 cross-snapshot address+area+rent repeats are flagged and kept.
