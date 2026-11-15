
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# 1. Configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CSV_PATH = Path(
    r"C:\Users\athar\OneDrive\Desktop\app_mietenspiegel_metadaten_EPSG_4326.csv"
)

TABLE_NAME = "raw_mietenspiegel_metadata"

load_dotenv(PROJECT_ROOT / ".env")

# 2. Read metadata CSV
if not CSV_PATH.exists():
    raise FileNotFoundError(f"File not found: {CSV_PATH}")

df = pd.read_csv(
    CSV_PATH,
    sep=";",
    encoding="utf-8-sig",
    dtype=str,
    keep_default_na=False
)

print("Source records:", len(df))
print("Source columns:", list(df.columns))

# 3. Rename source ID
df = df.rename(columns={"_fid": "source_id"})

required_columns = [
    "source_id",
    "erhebungsstand",
    "herausgeber",
    "hinweis",
    "titel",
    "merkmaletext",
    "coordinate_reference_system"
]

if set(df.columns) != set(required_columns):
    raise ValueError(
        f"Column mismatch. Found: {list(df.columns)}"
    )

df = df[required_columns]

# 4. Connect to MySQL
connection_url = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME")
)

engine = create_engine(connection_url, pool_pre_ping=True)

try:
    with engine.begin() as connection:

        existing_count = connection.execute(
            text(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        ).scalar()

        if existing_count > 0:
            raise RuntimeError(
                f"{TABLE_NAME} already contains {existing_count} records. "
                "Import stopped to prevent duplicates."
            )

        df.to_sql(
            name=TABLE_NAME,
            con=connection,
            if_exists="append",
            index=False
        )

    # 5. Verify import
    with engine.connect() as connection:
        final_count = connection.execute(
            text(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        ).scalar()

    print("\nINGESTION COMPLETED")
    print("Source records:", len(df))
    print("MySQL records:", final_count)

    if final_count == len(df):
        print("SUCCESS: Record counts match!")
    else:
        print("WARNING: Record counts do not match.")

finally:
    engine.dispose()
