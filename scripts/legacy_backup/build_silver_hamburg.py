
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from pathlib import Path


# =====================================================
# 1. CONFIGURATION
# =====================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

SOURCE_TABLE = "raw_rental_listings"
TARGET_TABLE = "stg_hamburg_listings"

DECIMAL_FIELDS = [
    "baseRent",
    "totalRent",
    "serviceCharge",
    "heatingCosts",
    "livingSpace",
    "noRooms",
]

INTEGER_FIELDS = [
    "yearConstructed",
]


# =====================================================
# 2. DATABASE CONNECTION
# =====================================================

connection_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(connection_url)


# =====================================================
# 3. CHECK SOURCE AND TARGET
# =====================================================

print("\nLETURA INTELLIGENCE - SILVER TRANSFORMATION")
print("=" * 55)

with engine.connect() as conn:

    source_count = conn.execute(
        text(f"SELECT COUNT(*) FROM `{SOURCE_TABLE}`")
    ).scalar()

    columns = conn.execute(
        text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """),
        {"table_name": SOURCE_TABLE}
    ).scalars().all()

    target_exists = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
        """),
        {"table_name": TARGET_TABLE}
    ).scalar()

if not columns:
    raise ValueError("Source table not found.")

if target_exists:
    raise RuntimeError(
        "Silver table already exists. "
        "Check it in MySQL before running again."
    )

print(f"Source records: {source_count:,}")
print(f"Source columns: {len(columns)}")


# =====================================================
# 4. BUILD TRANSFORMATION EXPRESSIONS
# =====================================================

select_expressions = []

for column in columns:

    quoted = f"`{column}`"

    if column in DECIMAL_FIELDS:

        expression = f"""
            CAST(
                NULLIF(
                    NULLIF(TRIM({quoted}), 'NA'),
                    ''
                ) AS DECIMAL(15,2)
            ) AS {quoted}
        """

    elif column in INTEGER_FIELDS:

        expression = f"""
            CAST(
                NULLIF(
                    NULLIF(TRIM({quoted}), 'NA'),
                    ''
                ) AS SIGNED
            ) AS {quoted}
        """

    else:
        expression = quoted

    select_expressions.append(expression)


# =====================================================
# 5. CONVERT LISTING DATE
# Source values: Sep18, May19, Oct19, Feb20
# Result: 2018-09-01, 2019-05-01, etc.
# =====================================================

month_expression = """
    CASE LOWER(LEFT(TRIM(`date`), 3))
        WHEN 'jan' THEN '01'
        WHEN 'feb' THEN '02'
        WHEN 'mar' THEN '03'
        WHEN 'apr' THEN '04'
        WHEN 'may' THEN '05'
        WHEN 'jun' THEN '06'
        WHEN 'jul' THEN '07'
        WHEN 'aug' THEN '08'
        WHEN 'sep' THEN '09'
        WHEN 'oct' THEN '10'
        WHEN 'nov' THEN '11'
        WHEN 'dec' THEN '12'
        ELSE NULL
    END
"""

date_expression = f"""
    CAST(
        CASE
            WHEN TRIM(`date`) REGEXP '^[A-Za-z]{{3}}[0-9]{{2}}$'
            THEN CONCAT(
                '20',
                RIGHT(TRIM(`date`), 2),
                '-',
                {month_expression},
                '-01'
            )
            ELSE NULL
        END AS DATE
    ) AS listing_date
"""

select_expressions.append(date_expression)


# =====================================================
# 6. CALCULATE RENT PER SQUARE METRE
# =====================================================

select_expressions.append("""
    ROUND(
        CAST(
            NULLIF(NULLIF(TRIM(`baseRent`), 'NA'), '')
            AS DECIMAL(15,2)
        )
        /
        NULLIF(
            CAST(
                NULLIF(NULLIF(TRIM(`livingSpace`), 'NA'), '')
                AS DECIMAL(15,2)
            ),
            0
        ),
        2
    ) AS rent_per_sqm
""")


# =====================================================
# 7. CREATE SILVER TABLE
# =====================================================

print("\nCreating Hamburg Silver table...")

create_query = f"""
    CREATE TABLE `{TARGET_TABLE}` AS
    SELECT
        {','.join(select_expressions)}
    FROM `{SOURCE_TABLE}`
    WHERE LOWER(TRIM(`regio1`)) = 'hamburg'
"""

with engine.begin() as conn:
    conn.execute(text(create_query))


# =====================================================
# 8. CREATE INDEXES
# =====================================================

print("Creating indexes...")

with engine.begin() as conn:

    conn.execute(text(f"""
        CREATE INDEX idx_silver_record_id
        ON `{TARGET_TABLE}` (`source_record_id`)
    """))

    conn.execute(text(f"""
        CREATE INDEX idx_silver_district
        ON `{TARGET_TABLE}` (`regio3`)
    """))

    conn.execute(text(f"""
        CREATE INDEX idx_silver_listing_date
        ON `{TARGET_TABLE}` (`listing_date`)
    """))


# =====================================================
# 9. VALIDATION
# =====================================================

print("\nValidating Silver table...")

with engine.connect() as conn:

    silver_count = conn.execute(
        text(f"SELECT COUNT(*) FROM `{TARGET_TABLE}`")
    ).scalar()

    validation = conn.execute(text(f"""
        SELECT
            COUNT(*) AS total_records,

            SUM(baseRent IS NULL) AS missing_base_rent,

            SUM(livingSpace IS NULL) AS missing_living_space,

            SUM(rent_per_sqm IS NULL) AS missing_rent_per_sqm,

            MIN(rent_per_sqm) AS minimum_rent_per_sqm,

            MAX(rent_per_sqm) AS maximum_rent_per_sqm

        FROM `{TARGET_TABLE}`
    """)).mappings().one()

    date_distribution = conn.execute(text(f"""
        SELECT
            listing_date,
            COUNT(*) AS listing_count
        FROM `{TARGET_TABLE}`
        GROUP BY listing_date
        ORDER BY listing_date
    """)).fetchall()

    samples = conn.execute(text(f"""
        SELECT
            regio3,
            baseRent,
            livingSpace,
            rent_per_sqm,
            listing_date
        FROM `{TARGET_TABLE}`
        LIMIT 10
    """)).fetchall()


# =====================================================
# 10. FINAL REPORT
# =====================================================

print("\n" + "=" * 55)
print("SILVER TRANSFORMATION REPORT")
print("=" * 55)

print(f"Source records: {source_count:,}")
print(f"Hamburg Silver records: {silver_count:,}")

print("\nQUALITY CHECKS")

for key, value in validation.items():
    print(f"{key}: {value}")

print("\nLISTING DATE DISTRIBUTION")

for row in date_distribution:
    print(row)

print("\nSAMPLE RECORDS")

for row in samples:
    print(row)

if silver_count != 3759:
    raise RuntimeError("Unexpected Hamburg record count.")

if validation["missing_base_rent"] > 0:
    raise RuntimeError("Missing base rent detected.")

if validation["missing_living_space"] > 0:
    raise RuntimeError("Missing living space detected.")

if validation["missing_rent_per_sqm"] > 0:
    raise RuntimeError("Rent per sqm calculation failed.")

if sum(row[1] for row in date_distribution) != silver_count:
    raise RuntimeError("Date distribution does not match row count.")

print("\nSUCCESS: Silver table created and validated!")

engine.dispose()
