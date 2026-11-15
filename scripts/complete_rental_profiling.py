
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


# ==========================================================
# 1. CONFIGURATION
# ==========================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(PROJECT_DIR / ".env")

TABLE = "raw_rental_listings"

EXPECTED_ROWS = 268850

NUMERIC_FIELDS = [
    "baseRent",
    "totalRent",
    "serviceCharge",
    "heatingCosts",
    "livingSpace",
    "noRooms",
    "yearConstructed",
]

DATE_FIELD = "date"

# Numeric values must be convertible to numbers.
# Empty values are handled separately.


# ==========================================================
# 2. DATABASE CONNECTION
# ==========================================================

required_env = [
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
]

missing_env = [
    key for key in required_env
    if not os.getenv(key)
]

if missing_env:
    raise ValueError(
        f"Missing environment variables: {missing_env}"
    )

connection_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(connection_url)


# ==========================================================
# 3. FETCH TABLE METADATA
# ==========================================================

print("\n" + "=" * 65)
print("LETURA INTELLIGENCE - RENTAL DATA QUALITY PROFILING")
print("=" * 65)

with engine.connect() as conn:

    columns = pd.read_sql(
        text("""
            SELECT
                COLUMN_NAME,
                DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """),
        conn,
        params={"table_name": TABLE}
    )

    total_rows = conn.execute(
        text(f"SELECT COUNT(*) FROM `{TABLE}`")
    ).scalar()

if columns.empty:
    raise ValueError(f"Table {TABLE} was not found.")

column_names = columns["COLUMN_NAME"].tolist()

print(f"\nTable: {TABLE}")
print(f"Total records: {total_rows:,}")
print(f"Total columns: {len(columns)}")

if total_rows == 0:
    raise ValueError("Rental table is empty.")


# ==========================================================
# 4. COLUMN COMPLETENESS AND UNIQUENESS
# ==========================================================

print("\n[1/6] Analysing column completeness...")

expressions = []

for i, column in enumerate(column_names):

    col = f"`{column}`"

    expressions.append(
        f"""
        SUM(
            CASE
                WHEN {col} IS NULL
                  OR TRIM(CAST({col} AS CHAR)) = ''
                THEN 1 ELSE 0
            END
        ) AS missing_{i}
        """
    )

    expressions.append(
        f"""
        COUNT(
            DISTINCT NULLIF(TRIM(CAST({col} AS CHAR)), '')
        ) AS distinct_{i}
        """
    )

profile_query = f"""
SELECT
    {','.join(expressions)}
FROM `{TABLE}`
"""

with engine.connect() as conn:
    profile_result = conn.execute(
        text(profile_query)
    ).mappings().one()

column_results = []

for i, row in columns.iterrows():

    missing = int(profile_result[f"missing_{i}"])
    distinct = int(profile_result[f"distinct_{i}"])

    complete = total_rows - missing

    column_results.append({
        "column_name": row["COLUMN_NAME"],
        "mysql_data_type": row["DATA_TYPE"],
        "total_records": total_rows,
        "missing_records": missing,
        "complete_records": complete,
        "missing_percentage": round(
            missing / total_rows * 100, 2
        ),
        "distinct_values": distinct,
    })

column_profile = pd.DataFrame(column_results)

column_profile = column_profile.sort_values(
    "missing_percentage",
    ascending=False
)

column_profile.to_csv(
    LOG_DIR / "column_quality_profile.csv",
    index=False
)


# ==========================================================
# 5. NUMERIC DATA QUALITY
# ==========================================================

print("[2/6] Checking numeric field validity...")

numeric_results = []

for field in NUMERIC_FIELDS:

    if field not in column_names:
        print(f"Skipping unavailable column: {field}")
        continue

    col = f"`{field}`"

    query = f"""
    SELECT
        SUM(
            CASE
                WHEN {col} IS NULL
                  OR TRIM({col}) = ''
                THEN 1 ELSE 0
            END
        ) AS missing_count,

        SUM(
            CASE
                WHEN {col} IS NOT NULL
                 AND TRIM({col}) <> ''
                 AND TRIM({col}) NOT REGEXP
                     '^[+-]?[0-9]+([.][0-9]+)?$'
                THEN 1 ELSE 0
            END
        ) AS invalid_numeric_count,

        MIN(
            CASE
                WHEN TRIM({col}) REGEXP
                    '^[+-]?[0-9]+([.][0-9]+)?$'
                THEN CAST({col} AS DECIMAL(20,4))
            END
        ) AS minimum_value,

        MAX(
            CASE
                WHEN TRIM({col}) REGEXP
                    '^[+-]?[0-9]+([.][0-9]+)?$'
                THEN CAST({col} AS DECIMAL(20,4))
            END
        ) AS maximum_value

    FROM `{TABLE}`
    """

    with engine.connect() as conn:
        result = conn.execute(
            text(query)
        ).mappings().one()

    numeric_results.append({
        "column_name": field,
        "missing_records": int(
            result["missing_count"] or 0
        ),
        "invalid_numeric_records": int(
            result["invalid_numeric_count"] or 0
        ),
        "minimum_value": result["minimum_value"],
        "maximum_value": result["maximum_value"],
    })

numeric_profile = pd.DataFrame(numeric_results)

numeric_profile.to_csv(
    LOG_DIR / "numeric_quality_profile.csv",
    index=False
)


# ==========================================================
# 6. BUSINESS VALIDATION: RENT AND APARTMENT SIZE
# ==========================================================

print("[3/6] Checking rental business rules...")

business_checks = {}

business_queries = {
    "zero_or_negative_base_rent": """
        SELECT COUNT(*)
        FROM raw_rental_listings
        WHERE TRIM(baseRent) REGEXP
            '^[+-]?[0-9]+([.][0-9]+)?$'
          AND CAST(baseRent AS DECIMAL(20,4)) <= 0
    """,

    "zero_or_negative_living_space": """
        SELECT COUNT(*)
        FROM raw_rental_listings
        WHERE TRIM(livingSpace) REGEXP
            '^[+-]?[0-9]+([.][0-9]+)?$'
          AND CAST(livingSpace AS DECIMAL(20,4)) <= 0
    """,

    "zero_or_negative_rooms": """
        SELECT COUNT(*)
        FROM raw_rental_listings
        WHERE TRIM(noRooms) REGEXP
            '^[+-]?[0-9]+([.][0-9]+)?$'
          AND CAST(noRooms AS DECIMAL(20,4)) <= 0
    """,

    "unusually_large_living_space_over_1000": """
        SELECT COUNT(*)
        FROM raw_rental_listings
        WHERE TRIM(livingSpace) REGEXP
            '^[+-]?[0-9]+([.][0-9]+)?$'
          AND CAST(livingSpace AS DECIMAL(20,4)) > 1000
    """
}

with engine.connect() as conn:

    for check_name, query in business_queries.items():

        business_checks[check_name] = conn.execute(
            text(query)
        ).scalar()


# ==========================================================
# 7. GEOGRAPHIC DISTRIBUTION
# ==========================================================

print("[4/6] Analysing geographic distribution...")

geographic_results = []

if "regio1" in column_names and "regio3" in column_names:

    query = """
        SELECT
            regio1 AS state,
            regio3 AS district,
            COUNT(*) AS listing_count
        FROM raw_rental_listings
        GROUP BY regio1, regio3
        ORDER BY listing_count DESC
    """

    with engine.connect() as conn:
        geographic_profile = pd.read_sql(
            text(query),
            conn
        )

    geographic_profile.to_csv(
        LOG_DIR / "geographic_profile.csv",
        index=False
    )

else:
    geographic_profile = pd.DataFrame()


# ==========================================================
# 8. HAMBURG DATA QUALITY
# ==========================================================

print("[5/6] Analysing Hamburg records...")

hamburg_results = {}

with engine.connect() as conn:

    hamburg_count = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM raw_rental_listings
            WHERE LOWER(TRIM(regio1)) = 'hamburg'
        """)
    ).scalar()

    hamburg_results["total_hamburg_listings"] = hamburg_count

    fields_to_check = [
        "baseRent",
        "livingSpace",
        "noRooms",
        "regio3",
        "street",
        "yearConstructed",
        "totalRent",
    ]

    for field in fields_to_check:

        if field not in column_names:
            continue

        query = text(f"""
            SELECT
                SUM(
                    CASE
                        WHEN `{field}` IS NULL
                          OR TRIM(`{field}`) = ''
                        THEN 1 ELSE 0
                    END
                )
            FROM raw_rental_listings
            WHERE LOWER(TRIM(regio1)) = 'hamburg'
        """)

        missing = conn.execute(query).scalar() or 0

        hamburg_results[f"{field}_missing"] = int(missing)

        hamburg_results[f"{field}_missing_percentage"] = round(
            missing / hamburg_count * 100, 2
        ) if hamburg_count else 0


# ==========================================================
# 9. DATE DISTRIBUTION
# ==========================================================

print("[6/6] Analysing listing snapshots...")

date_profile = pd.DataFrame()

if DATE_FIELD in column_names:

    with engine.connect() as conn:

        date_profile = pd.read_sql(
            text(f"""
                SELECT
                    `{DATE_FIELD}` AS listing_date,
                    COUNT(*) AS listing_count
                FROM `{TABLE}`
                GROUP BY `{DATE_FIELD}`
                ORDER BY `{DATE_FIELD}`
            """),
            conn
        )


# ==========================================================
# 10. SAVE FINAL SUMMARY
# ==========================================================

summary_path = LOG_DIR / "rental_quality_summary.txt"

with open(summary_path, "w", encoding="utf-8") as file:

    file.write("LETURA INTELLIGENCE - DATA QUALITY REPORT\n")
    file.write("=" * 55 + "\n\n")

    file.write(f"Total records: {total_rows:,}\n")
    file.write(f"Total columns: {len(columns)}\n")
    file.write(
        f"Expected initial record count: {EXPECTED_ROWS:,}\n"
    )

    file.write("\nCOLUMN COMPLETENESS\n")
    file.write("-" * 55 + "\n")

    file.write(
        column_profile.to_string(index=False)
    )

    file.write("\n\nNUMERIC QUALITY\n")
    file.write("-" * 55 + "\n")

    file.write(
        numeric_profile.to_string(index=False)
    )

    file.write("\n\nBUSINESS VALIDATION\n")
    file.write("-" * 55 + "\n")

    for name, value in business_checks.items():
        file.write(f"{name}: {value:,}\n")

    file.write("\nHAMBURG DATA QUALITY\n")
    file.write("-" * 55 + "\n")

    for name, value in hamburg_results.items():
        file.write(f"{name}: {value}\n")

    file.write("\nLISTING DATE DISTRIBUTION\n")
    file.write("-" * 55 + "\n")

    file.write(date_profile.to_string(index=False))


# ==========================================================
# 11. DISPLAY IMPORTANT RESULTS
# ==========================================================

print("\n" + "=" * 65)
print("PROFILING COMPLETED")
print("=" * 65)

print(f"Total records: {total_rows:,}")
print(f"Total columns: {len(columns)}")

print("\nTOP 15 COLUMNS WITH MISSING VALUES")

print(
    column_profile[
        [
            "column_name",
            "missing_records",
            "missing_percentage"
        ]
    ].head(15).to_string(index=False)
)

print("\nNUMERIC DATA QUALITY")

print(numeric_profile.to_string(index=False))

print("\nBUSINESS VALIDATION")

for name, value in business_checks.items():
    print(f"{name}: {value:,}")

print("\nHAMBURG SUMMARY")

for name, value in hamburg_results.items():
    print(f"{name}: {value}")

print("\nLISTING DATE DISTRIBUTION")
print(date_profile.to_string(index=False))

print("\nREPORT FILES CREATED:")
print("1. logs/column_quality_profile.csv")
print("2. logs/numeric_quality_profile.csv")
print("3. logs/geographic_profile.csv")
print("4. logs/rental_quality_summary.txt")

engine.dispose()

print("\nDATABASE CONNECTION CLOSED.")
print("Raw source data was not modified.")
