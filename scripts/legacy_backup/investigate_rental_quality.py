
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


# ------------------------------------------
# CONFIGURATION
# ------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(PROJECT_DIR / ".env")

url = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(url)

FIELDS = [
    "baseRent",
    "totalRent",
    "serviceCharge",
    "heatingCosts",
    "livingSpace",
    "noRooms",
    "yearConstructed",
]

PLACEHOLDERS = [
    "NA", "N/A", "NULL", "NONE", "NAN",
    "UNKNOWN", "NOT AVAILABLE", "-", "-1"
]


# ------------------------------------------
# 1. INVESTIGATE MISSING VALUE REPRESENTATION
# ------------------------------------------

print("\nMISSING VALUE REPRESENTATION")
print("=" * 60)

placeholder_results = []

with engine.connect() as conn:

    for field in FIELDS:

        query = text(f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE
                    WHEN `{field}` IS NULL THEN 1 ELSE 0
                END) AS sql_nulls,
                SUM(CASE
                    WHEN TRIM(UPPER(CAST(`{field}` AS CHAR)))
                         IN :placeholders
                    THEN 1 ELSE 0
                END) AS placeholder_count
            FROM raw_rental_listings
        """)

        # Use explicit SQL literals for the placeholder list
        values = ",".join(
            f"'{value}'" for value in PLACEHOLDERS
        )

        query = text(f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE
                    WHEN `{field}` IS NULL THEN 1 ELSE 0
                END) AS sql_nulls,
                SUM(CASE
                    WHEN UPPER(TRIM(CAST(`{field}` AS CHAR)))
                         IN ({values})
                    THEN 1 ELSE 0
                END) AS placeholder_count
            FROM raw_rental_listings
        """)

        result = conn.execute(query).mappings().one()

        placeholder_results.append({
            "field": field,
            "sql_nulls": result["sql_nulls"],
            "placeholder_values": result["placeholder_count"],
        })

placeholder_df = pd.DataFrame(placeholder_results)

print(placeholder_df.to_string(index=False))


# ------------------------------------------
# 2. INVESTIGATE NON-NUMERIC VALUES
# ------------------------------------------

print("\nNON-NUMERIC VALUE SAMPLES")
print("=" * 60)

invalid_results = []

for field in FIELDS:

    query = text(f"""
        SELECT
            TRIM(CAST(`{field}` AS CHAR)) AS value,
            COUNT(*) AS frequency
        FROM raw_rental_listings
        WHERE `{field}` IS NOT NULL
          AND TRIM(CAST(`{field}` AS CHAR)) <> ''
          AND TRIM(CAST(`{field}` AS CHAR))
              NOT REGEXP '^[+-]?[0-9]+([.][0-9]+)?$'
        GROUP BY TRIM(CAST(`{field}` AS CHAR))
        ORDER BY frequency DESC
        LIMIT 10
    """)

    with engine.connect() as conn:
        result_df = pd.read_sql(query, conn)

    for _, row in result_df.iterrows():

        invalid_results.append({
            "field": field,
            "value": row["value"],
            "frequency": row["frequency"],
        })

    print(f"\n{field}:")
    if result_df.empty:
        print("No invalid values.")
    else:
        print(result_df.to_string(index=False))


pd.DataFrame(invalid_results).to_csv(
    LOG_DIR / "invalid_numeric_values.csv",
    index=False
)


# ------------------------------------------
# 3. HAMBURG-SPECIFIC VALIDATION
# ------------------------------------------

print("\nHAMBURG DATA QUALITY")
print("=" * 60)

hamburg_results = []

for field in FIELDS:

    query = text(f"""
        SELECT
            COUNT(*) AS total_records,

            SUM(CASE
                WHEN `{field}` IS NULL
                  OR TRIM(CAST(`{field}` AS CHAR)) = ''
                THEN 1 ELSE 0
            END) AS empty_records,

            SUM(CASE
                WHEN `{field}` IS NOT NULL
                 AND TRIM(CAST(`{field}` AS CHAR)) <> ''
                 AND TRIM(CAST(`{field}` AS CHAR))
                     NOT REGEXP '^[+-]?[0-9]+([.][0-9]+)?$'
                THEN 1 ELSE 0
            END) AS invalid_numeric_records

        FROM raw_rental_listings
        WHERE LOWER(TRIM(regio1)) = 'hamburg'
    """)

    with engine.connect() as conn:
        result = conn.execute(query).mappings().one()

    hamburg_results.append({
        "field": field,
        "total_records": result["total_records"],
        "empty_records": result["empty_records"],
        "invalid_numeric_records":
            result["invalid_numeric_records"],
    })

hamburg_df = pd.DataFrame(hamburg_results)

print(hamburg_df.to_string(index=False))

hamburg_df.to_csv(
    LOG_DIR / "hamburg_numeric_quality.csv",
    index=False
)


# ------------------------------------------
# 4. INVALID BUSINESS VALUES IN HAMBURG
# ------------------------------------------

print("\nHAMBURG BUSINESS VALIDATION")
print("=" * 60)

checks = {
    "Zero or negative rent": """
        CAST(baseRent AS DECIMAL(20,4)) <= 0
        AND TRIM(baseRent) REGEXP '^[+-]?[0-9]+([.][0-9]+)?$'
    """,

    "Zero or negative apartment area": """
        CAST(livingSpace AS DECIMAL(20,4)) <= 0
        AND TRIM(livingSpace) REGEXP '^[+-]?[0-9]+([.][0-9]+)?$'
    """,

    "Apartment area above 1000 m2": """
        CAST(livingSpace AS DECIMAL(20,4)) > 1000
        AND TRIM(livingSpace) REGEXP '^[+-]?[0-9]+([.][0-9]+)?$'
    """,
}

with engine.connect() as conn:

    for label, condition in checks.items():

        count = conn.execute(text(f"""
            SELECT COUNT(*)
            FROM raw_rental_listings
            WHERE LOWER(TRIM(regio1)) = 'hamburg'
              AND ({condition})
        """)).scalar()

        print(f"{label}: {count}")


# ------------------------------------------
# FINAL
# ------------------------------------------

print("\nREPORTS CREATED")
print("-" * 60)
print("logs/invalid_numeric_values.csv")
print("logs/hamburg_numeric_quality.csv")

engine.dispose()

print("\nInvestigation completed.")
print("No database records were modified.")
