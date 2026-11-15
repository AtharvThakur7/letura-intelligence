"""Deterministic, testable transformation rules for the Hamburg listings.

Rules here never delete rows and never overwrite source values: every
derived value goes into a *new* column and raw columns are preserved.
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

import pandas as pd

MISSING_TOKENS = {"", "na", "n/a", "nan", "none", "null", "no_information"}

SNAPSHOT_LABELS = {
    date(2018, 9, 1): "Sep 2018",
    date(2019, 5, 1): "May 2019",
    date(2019, 10, 1): "Oct 2019",
    date(2020, 2, 1): "Feb 2020",
}
EXPECTED_SNAPSHOT_COUNTS = {"Sep 2018": 673, "May 2019": 1071, "Oct 2019": 902, "Feb 2020": 1113}
SNAPSHOT_ORDER = list(EXPECTED_SNAPSHOT_COUNTS)

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


# --------------------------------------------------------------------------
# Missing tokens, booleans, numbers, dates
# --------------------------------------------------------------------------
def is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN
        return True
    return str(value).strip().lower() in MISSING_TOKENS


def to_number(value) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def to_bool(value) -> bool | None:
    if is_missing(value):
        return None
    v = str(value).strip().lower()
    if v in {"true", "1", "yes", "y", "ja"}:
        return True
    if v in {"false", "0", "no", "n", "nein"}:
        return False
    return None


def parse_snapshot_date(value) -> date | None:
    """'Sep18' -> date(2018, 9, 1). Returns None for anything unexpected."""
    if is_missing(value):
        return None
    m = re.fullmatch(r"([A-Za-z]{3})(\d{2})", str(value).strip())
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    return date(2000 + int(m.group(2)), _MONTHS[m.group(1).lower()], 1)


def snapshot_label(d) -> str | None:
    if d is None or (isinstance(d, float) and d != d):
        return None
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return SNAPSHOT_LABELS.get(d, d.strftime("%b %Y") if hasattr(d, "strftime") else None)


def rent_per_sqm(base_rent, living_space) -> float | None:
    """Cold base rent / living area, rounded to 2 dp. None if not computable."""
    br, ls = to_number(base_rent), to_number(living_space)
    if br is None or ls is None or ls <= 0:
        return None
    return round(br / ls, 2)


# --------------------------------------------------------------------------
# Neighbourhood (Stadtteil) names and Bezirk mapping
# --------------------------------------------------------------------------
_NAME_OVERRIDES = {
    "Hamb._Altstadt": "Hamburg-Altstadt",
    "St._Pauli": "St. Pauli",
    "St._Georg": "St. Georg",
    "Groß_Borstel": "Groß Borstel",
    "Groß_Flottbek": "Groß Flottbek",
}


def neighbourhood_name(regio3) -> str | None:
    if is_missing(regio3):
        return None
    raw = str(regio3).strip()
    return _NAME_OVERRIDES.get(raw, raw.replace("_", "-"))


# Official administrative assignment of Hamburg Stadtteile to the 7 Bezirke.
BEZIRK_MAP: dict[str, str] = {}
for _bezirk, _names in {
    "Hamburg-Mitte": ["Hamburg-Altstadt", "HafenCity", "Neustadt", "St. Pauli", "St. Georg", "Hammerbrook",
                      "Borgfelde", "Hamm", "Hamm-Mitte", "Hamm-Nord", "Hamm-Süd", "Horn", "Billstedt", "Billbrook",
                      "Rothenburgsort", "Veddel", "Wilhelmsburg", "Kleiner Grasbrook", "Steinwerder",
                      "Waltershof", "Finkenwerder", "Neuwerk"],
    "Altona": ["Altona-Altstadt", "Sternschanze", "Altona-Nord", "Ottensen", "Bahrenfeld", "Groß Flottbek",
               "Othmarschen", "Lurup", "Osdorf", "Nienstedten", "Blankenese", "Iserbrook", "Sülldorf", "Rissen"],
    "Eimsbüttel": ["Eimsbüttel", "Rotherbaum", "Harvestehude", "Hoheluft-West", "Lokstedt", "Niendorf",
                   "Schnelsen", "Eidelstedt", "Stellingen"],
    "Hamburg-Nord": ["Hoheluft-Ost", "Eppendorf", "Groß Borstel", "Alsterdorf", "Winterhude", "Uhlenhorst",
                     "Hohenfelde", "Barmbek-Süd", "Dulsberg", "Barmbek-Nord", "Ohlsdorf", "Fuhlsbüttel",
                     "Langenhorn"],
    "Wandsbek": ["Eilbek", "Wandsbek", "Marienthal", "Jenfeld", "Tonndorf", "Farmsen-Berne", "Bramfeld",
                 "Steilshoop", "Wellingsbüttel", "Sasel", "Poppenbüttel", "Hummelsbüttel",
                 "Lemsahl-Mellingstedt", "Duvenstedt", "Wohldorf-Ohlstedt", "Bergstedt", "Volksdorf",
                 "Rahlstedt"],
    "Bergedorf": ["Lohbrügge", "Bergedorf", "Curslack", "Altengamme", "Neuengamme", "Kirchwerder",
                  "Ochsenwerder", "Reitbrook", "Allermöhe", "Neuallermöhe", "Billwerder", "Moorfleet",
                  "Tatenberg", "Spadenland"],
    "Harburg": ["Harburg", "Neuland", "Gut Moor", "Wilstorf", "Rönneburg", "Langenbek", "Sinstorf",
                "Marmstorf", "Eißendorf", "Heimfeld", "Moorburg", "Altenwerder", "Hausbruch",
                "Neugraben-Fischbek", "Francop", "Neuenfelde", "Cranz"],
}.items():
    for _n in _names:
        BEZIRK_MAP[_n] = _bezirk


def bezirk_for(neighbourhood: str | None) -> str | None:
    return BEZIRK_MAP.get(neighbourhood) if neighbourhood else None


# --------------------------------------------------------------------------
# Banding
# --------------------------------------------------------------------------
SIZE_BANDS = [(0, 40, "< 40 m²"), (40, 60, "40–60 m²"), (60, 80, "60–80 m²"), (80, 100, "80–100 m²"),
              (100, 130, "100–130 m²"), (130, float("inf"), "≥ 130 m²")]
SIZE_BAND_ORDER = [b[2] for b in SIZE_BANDS]
ROOM_BAND_ORDER = ["1", "1.5–2", "2.5–3", "3.5–4", "4.5+"]
YEAR_BAND_ORDER = ["Before 1919", "1919–1948", "1949–1960", "1961–1977", "1978–1993", "1994–2010",
                   "2011–2015", "2016–2020"]


def size_band(area) -> str | None:
    a = to_number(area)
    if a is None:
        return None
    for lo, hi, label in SIZE_BANDS:
        if lo <= a < hi:
            return label
    return None


def room_band(rooms) -> str | None:
    r = to_number(rooms)
    if r is None:
        return None
    if r <= 1:
        return "1"
    if r <= 2:
        return "1.5–2"
    if r <= 3:
        return "2.5–3"
    if r <= 4:
        return "3.5–4"
    return "4.5+"


MIN_PLAUSIBLE_YEAR = 1800
MAX_PLAUSIBLE_YEAR = 2020  # latest snapshot is Feb 2020


def year_band(year) -> str | None:
    y = to_number(year)
    if y is None or not (MIN_PLAUSIBLE_YEAR <= y <= MAX_PLAUSIBLE_YEAR + 1):
        return None
    y = int(y)
    for hi, label in [(1918, "Before 1919"), (1948, "1919–1948"), (1960, "1949–1960"), (1977, "1961–1977"),
                      (1993, "1978–1993"), (2010, "1994–2010"), (2015, "2011–2015")]:
        if y <= hi:
            return label
    return "2016–2020"


# --------------------------------------------------------------------------
# Mietenspiegel 2025 characteristic mapping
# --------------------------------------------------------------------------
MS_PERIODS = [
    "bis 31.12.1918", "01.01.1919 bis 20.06.1948", "21.06.1948 bis 31.12.1960", "1961 bis 1967",
    "1968 bis 1977", "1978 bis 1993", "1994 bis 2010", "2011 bis 2015", "2016 bis 2020", "2021 bis 2024",
]
MS_LOCATIONS = {"normal": "Normale Wohnlage", "gut": "Gute Wohnlage"}
MS_AREA_NORMAL = [(0, 41, "bis unter 41m²"), (41, 66, "41m² bis unter 66m²"), (66, 91, "66m² bis unter 91m²"),
                  (91, float("inf"), "ab 91m²")]
MS_AREA_GOOD = MS_AREA_NORMAL[:3] + [(91, 131, "91m² bis unter 131m²"), (131, float("inf"), "ab 131m²")]
MS_AREA_ORDER = ["bis unter 41m²", "41m² bis unter 66m²", "66m² bis unter 91m²", "ab 91m²",
                 "91m² bis unter 131m²", "ab 131m²"]


def ms_construction_period(year) -> str | None:
    """Map a construction year to the Mietenspiegel Baualtersklasse.

    1948 is deliberately left unmapped: the official boundary is 20.06.1948 and
    a year alone cannot place the building on either side.
    """
    y = to_number(year)
    if y is None or not (MIN_PLAUSIBLE_YEAR <= y <= 2024):
        return None
    y = int(y)
    if y <= 1918:
        return MS_PERIODS[0]
    if y <= 1947:
        return MS_PERIODS[1]
    if y == 1948:
        return None
    for hi, label in [(1960, MS_PERIODS[2]), (1967, MS_PERIODS[3]), (1977, MS_PERIODS[4]), (1993, MS_PERIODS[5]),
                      (2010, MS_PERIODS[6]), (2015, MS_PERIODS[7]), (2020, MS_PERIODS[8])]:
        if y <= hi:
            return label
    return MS_PERIODS[9]


def ms_area_category(area, location_class: str | None) -> str | None:
    """Living-area category. Bands above 91 m² differ between normal and good locations."""
    a = to_number(area)
    if a is None or a <= 0:
        return None
    loc = None if is_missing(location_class) else str(location_class).lower()
    if loc is None and a >= 91:
        return None  # bands above 91 m² depend on the (unknown) Wohnlage – do not guess
    bands = MS_AREA_GOOD if loc == "gut" else MS_AREA_NORMAL
    for lo, hi, label in bands:
        if lo <= a < hi:
            return label
    return None


# --------------------------------------------------------------------------
# Address normalisation and Wohnlagen matching (conservative)
# --------------------------------------------------------------------------
_TRANSLIT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def decode_street(raw) -> str | None:
    """HTML-decode + Unicode NFC. Returns a readable street name (raw is preserved separately)."""
    if is_missing(raw):
        return None
    return unicodedata.normalize("NFC", html.unescape(str(raw))).strip()


def street_key(raw) -> str | None:
    """Matching key: decoded, lower-cased, transliterated, 'straße/str.' unified, punctuation removed."""
    s = decode_street(raw)
    if not s:
        return None
    s = s.lower().translate(_TRANSLIT)
    s = re.sub(r"strasse\b|str\.|str\b", "str", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s or None


@dataclass(frozen=True, order=True)
class HouseNumber:
    number: int
    suffix: str = ""

    @property
    def parity(self) -> str:
        return "U" if self.number % 2 else "G"


def parse_house_number(raw) -> HouseNumber | None:
    """'9a' -> (9,'a'), '012' -> (12,''), '12-14' -> (12,''), 'NA' -> None."""
    if is_missing(raw):
        return None
    m = re.match(r"\s*0*(\d+)\s*([a-zA-Z]?)", str(raw))
    if not m:
        return None
    return HouseNumber(int(m.group(1)), m.group(2).lower())


@dataclass
class LocationMatch:
    status: str                 # matched | ambiguous | unmatched_street | unmatched_number | no_address
    location_class: str | None = None
    location_score: float | None = None
    candidates: int = 0
    location_id: int | None = None


class LocationIndex:
    """In-memory index of the Wohnlagenverzeichnis by normalised street key."""

    def __init__(self, locations: pd.DataFrame):
        self.by_street: dict[str, list[tuple]] = {}
        for row in locations.itertuples(index=False):
            key = street_key(row.street)
            start = parse_house_number(row.house_number_start)
            end = parse_house_number(row.house_number_end)
            if not key or start is None or end is None:
                continue
            self.by_street.setdefault(key, []).append(
                (start, end, str(row.numbering_type).upper(), str(row.location_class).lower(),
                 float(row.location_score) if row.location_score is not None else None, int(row.location_id))
            )

    def match(self, street, house_number) -> LocationMatch:
        key = street_key(street)
        hn = parse_house_number(house_number)
        if not key or hn is None:
            return LocationMatch("no_address")
        ranges = self.by_street.get(key)
        if not ranges:
            return LocationMatch("unmatched_street")
        cands = [r for r in ranges
                 if r[0] <= hn <= r[1] and (r[2] == "S" or r[2] == hn.parity)]
        if not cands:
            return LocationMatch("unmatched_number")
        classes = {c[3] for c in cands}
        if len(classes) > 1:
            return LocationMatch("ambiguous", candidates=len(cands))
        scores = [c[4] for c in cands if c[4] is not None]
        return LocationMatch(
            "matched",
            location_class=cands[0][3],
            location_score=round(sum(scores) / len(scores), 3) if scores else None,
            candidates=len(cands),
            location_id=cands[0][5] if len(cands) == 1 else None,
        )
