"""Dashboard filter state shared by all pages and the AI analyst."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import pandas as pd

AMENITIES = {"has_balcony": "Balcony", "has_garden": "Garden", "has_lift": "Lift",
             "has_kitchen": "Fitted kitchen", "is_new_construction": "New construction", "has_cellar": "Cellar"}


@dataclass
class FilterState:
    snapshots: list[str] = field(default_factory=list)        # empty = all
    neighbourhoods: list[str] = field(default_factory=list)
    property_types: list[str] = field(default_factory=list)
    rooms: list[str] = field(default_factory=list)            # room_band values
    area_range: tuple[float, float] | None = None
    year_range: tuple[int, int] | None = None                 # applies only to rows with a year
    amenities: list[str] = field(default_factory=list)        # all selected must be True

    def is_active(self) -> bool:
        return any([self.snapshots, self.neighbourhoods, self.property_types, self.rooms,
                    self.area_range, self.year_range, self.amenities])

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}

    def describe(self) -> str:
        if not self.is_active():
            return "No filters (all 3,759 Hamburg listings)"
        parts = []
        if self.snapshots: parts.append("Snapshot: " + ", ".join(self.snapshots))
        if self.neighbourhoods: parts.append("Neighbourhood: " + ", ".join(self.neighbourhoods))
        if self.property_types: parts.append("Type: " + ", ".join(self.property_types))
        if self.rooms: parts.append("Rooms: " + ", ".join(self.rooms))
        if self.area_range: parts.append(f"Area: {self.area_range[0]:.0f}–{self.area_range[1]:.0f} m²")
        if self.year_range: parts.append(f"Built: {self.year_range[0]}–{self.year_range[1]}")
        if self.amenities: parts.append("Amenities: " + ", ".join(AMENITIES.get(a, a) for a in self.amenities))
        return "; ".join(parts)


def apply_filters(df: pd.DataFrame, f: FilterState) -> pd.DataFrame:
    """Filter without ever mutating the source frame. Missing values never match a range filter."""
    m = pd.Series(True, index=df.index)
    if f.snapshots: m &= df["snapshot"].astype(str).isin(f.snapshots)
    if f.neighbourhoods: m &= df["neighbourhood"].isin(f.neighbourhoods)
    if f.property_types: m &= df["property_type"].isin(f.property_types)
    if f.rooms: m &= df["room_band"].isin(f.rooms)
    if f.area_range: m &= df["livingSpace"].between(*f.area_range)
    if f.year_range: m &= df["yearConstructed"].between(*f.year_range)
    for a in f.amenities:
        if a in AMENITIES: m &= df[a].fillna(False).astype(bool)
    return df[m]
