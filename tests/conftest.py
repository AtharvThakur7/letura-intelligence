import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import pytest

from letura.analytics import transforms as T


def make_fixture() -> pd.DataFrame:
    """Small deterministic in-memory listings frame (no database needed)."""
    rows = []
    rid = 0
    for snap, d in [("Sep 2018", "2018-09-01"), ("Feb 2020", "2020-02-01")]:
        for nbh, base, area, rooms in [("Horn", 800, 60, 2), ("Horn", 900, 70, 3), ("Eppendorf", 1500, 75, 3), ("Eppendorf", 2000, 80, 3),
                                       ("Eppendorf", 99999, 50, 2)]:  # last one is an extreme outlier that must be kept
            rid += 1
            rows.append(dict(source_record_id=rid, scoutId=str(rid), snapshot=snap, listing_date=pd.Timestamp(d), neighbourhood=nbh,
                             bezirk="X", property_type="apartment", baseRent=base, livingSpace=area, noRooms=rooms,
                             rent_per_sqm=round(base / area, 2), yearConstructed=1990.0 + rid, has_balcony=bool(rid % 2), has_garden=False,
                             has_lift=True, has_kitchen=True, is_new_construction=False, has_cellar=True, size_band=T.size_band(area),
                             room_band=T.room_band(rooms), year_band=T.year_band(1990 + rid), outlier_iqr_global="normal", is_flagged=False,
                             location_class=None, quality_flags=None, street_decoded="Teststr.", geo_plz="20000", totalRent=base + 100))
    df = pd.DataFrame(rows)
    df["snapshot"] = pd.Categorical(df["snapshot"], categories=T.SNAPSHOT_ORDER, ordered=True)
    return df


@pytest.fixture
def listings() -> pd.DataFrame:
    return make_fixture()


def db_available() -> bool:
    try:
        from letura.db import admin_engine
        from sqlalchemy import text
        with admin_engine().connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not db_available(), reason="MySQL not reachable")
