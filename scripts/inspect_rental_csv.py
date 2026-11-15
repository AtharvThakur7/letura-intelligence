
import csv
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import os

# Project configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = Path(
    r"C:\Users\athar\OneDrive\Desktop\immo_data.csv"
)

load_dotenv(PROJECT_ROOT / ".env")

# Detect CSV delimiter
with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as file:
    sample = file.read(65536)

try:
    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    delimiter = dialect.delimiter
except csv.Error:
    delimiter = ","

print("CSV file found:", CSV_PATH.exists())
print("Detected delimiter:", repr(delimiter))

# Read only the header and first five records
df = pd.read_csv(
    CSV_PATH,
    sep=delimiter,
    nrows=5,
    dtype=str,
    encoding="utf-8-sig"
)

csv_columns = list(df.columns)

print("\nTotal CSV columns:", len(csv_columns))
print("\nCSV column names:")
for column in csv_columns:
    print("-", column)

# Connect to MySQL
connection_url = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME")
)

engine = create_engine(connection_url)

try:
    with engine.connect() as connection:
        result = connection.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'letura_intelligence'
              AND TABLE_NAME = 'raw_rental_listings'
            ORDER BY ORDINAL_POSITION
        """))

        db_columns = [
            row[0] for row in result.fetchall()
            if row[0] not in ("source_record_id", "loaded_at")
        ]

    print("\nMySQL source columns:", len(db_columns))

    missing_in_db = set(csv_columns) - set(db_columns)
    missing_in_csv = set(db_columns) - set(csv_columns)

    print("\nColumns missing in MySQL:", missing_in_db)
    print("Columns missing in CSV:", missing_in_csv)

    if not missing_in_db and not missing_in_csv:
        print("\nSUCCESS: CSV and MySQL columns match!")
    else:
        print("\nWARNING: Column mismatch found. Do not import yet.")

finally:
    engine.dispose()
