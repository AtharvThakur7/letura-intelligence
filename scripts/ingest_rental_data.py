
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# --------------------------------------------------
# 1. Project configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CSV_PATH = Path(
    r"C:\Users\athar\OneDrive\Desktop\immo_data.csv"
)

CHUNK_SIZE = 5000
TABLE_NAME = "raw_rental_listings"

load_dotenv(PROJECT_ROOT / ".env")

# --------------------------------------------------
# 2. MySQL connection
# --------------------------------------------------

connection_url = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME")
)

engine = create_engine(
    connection_url,
    pool_pre_ping=True
)

# --------------------------------------------------
# 3. Validate source file and target table
# --------------------------------------------------

if not CSV_PATH.exists():
    raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

with engine.connect() as connection:
    existing_rows = connection.execute(
        text(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    ).scalar()

if existing_rows > 0:
    raise RuntimeError(
        f"{TABLE_NAME} already contains {existing_rows} rows. "
        "Import stopped to prevent duplicate records."
    )

# --------------------------------------------------
# 4. Read and load CSV in chunks
# --------------------------------------------------

total_loaded = 0
start_time = time.time()

print("Starting rental data ingestion...")
print("Source:", CSV_PATH)
print("Target table:", TABLE_NAME)

try:
    chunks = pd.read_csv(
        CSV_PATH,
        sep=",",
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False,
        chunksize=CHUNK_SIZE,
        on_bad_lines="error"
    )

    for chunk_number, chunk in enumerate(chunks, start=1):

        # Load the current batch into MySQL
        chunk.to_sql(
            name=TABLE_NAME,
            con=engine,
            if_exists="append",
            index=False,
            chunksize=500,
            method=None
        )

        total_loaded += len(chunk)

        elapsed = round(time.time() - start_time, 2)

        print(
            f"Batch {chunk_number} completed | "
            f"Rows loaded: {total_loaded:,} | "
            f"Time: {elapsed} seconds"
        )

    # --------------------------------------------------
    # 5. Verify final row count
    # --------------------------------------------------

    with engine.connect() as connection:
        final_count = connection.execute(
            text(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        ).scalar()

    print("\nINGESTION COMPLETED")
    print("Rows processed:", f"{total_loaded:,}")
    print("Rows in MySQL:", f"{final_count:,}")
    print("Total time:", round(time.time() - start_time, 2), "seconds")

    if final_count == total_loaded:
        print("SUCCESS: Row counts match!")
    else:
        print("WARNING: Row counts do not match. Investigate before proceeding.")

except Exception as error:
    print("\nINGESTION FAILED")
    print("Error:", error)
    print("Rows successfully processed before failure:", total_loaded)

finally:
    engine.dispose()
