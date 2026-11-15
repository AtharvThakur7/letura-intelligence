
import os
import re
from pathlib import Path

import pdfplumber
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent

PDF_PATH = Path(
    r"C:\Users\athar\Downloads\d-wohnlagenverzeichnis-2025-data.pdf"
)

LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

UNMATCHED_FILE = LOG_DIR / "location_pdf_unmatched.txt"

load_dotenv(PROJECT_DIR / ".env")


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

connection_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(connection_url)


# --------------------------------------------------
# PDF PARSER
# --------------------------------------------------

house_number = r"\d+[a-zA-Z]*(?:-\d+[a-zA-Z]*)?"

pattern = re.compile(
    rf"^(.*?)\s+({house_number})\s*-\s*"
    rf"({house_number})\s+([UGS])\s+"
    rf"(normal|gut)\s+([\d,]+)$",
    re.IGNORECASE
)


# --------------------------------------------------
# EXTRACT RECORDS
# --------------------------------------------------

records = []
unmatched_lines = []

print("Starting residential location ingestion...")
 
with pdfplumber.open(PDF_PATH) as pdf:

    print(f"Total PDF pages: {len(pdf.pages)}")

    for page_index in range(2, len(pdf.pages)):

        page_number = page_index + 1
        page_text = pdf.pages[page_index].extract_text()

        if not page_text:
            continue

        for line in page_text.splitlines():

            line = line.strip()

            if not line:
                continue

            # Ignore repeated PDF numbering footnotes
            if (
                "ungerade" in line.lower()
                and "gerade" in line.lower()
                and "sonderfälle" in line.lower()
            ):
                continue

            match = pattern.match(line)

            if match:

                street, start, end, numbering, location, score = (
                    match.groups()
                )

                records.append({
                    "street": street.strip(),
                    "house_number_start": start,
                    "house_number_end": end,
                    "numbering_type": numbering.upper(),
                    "location_class": location.lower(),
                    "location_score": float(
                        score.replace(",", ".")
                    ),
                    "source_page": page_number
                })

            else:

                if (
                    "Wohnlagenverzeichnis" in line
                    or (
                        "Straße" in line
                        and "Hausnummer" in line
                    )
                ):
                    continue

                unmatched_lines.append(
                    f"Page {page_number}: {line}"
                )


# --------------------------------------------------
# DATAFRAME AND VALIDATION
# --------------------------------------------------

df = pd.DataFrame(records)

if df.empty:
    raise ValueError("No records extracted. Ingestion cancelled.")

print("\nEXTRACTION SUMMARY")
print("------------------")
print(f"Extracted records: {len(df)}")
print(f"Unmatched lines skipped: {len(unmatched_lines)}")

# Save skipped lines for audit
UNMATCHED_FILE.write_text(
    "\n".join(unmatched_lines),
    encoding="utf-8"
)

required_columns = [
    "street",
    "house_number_start",
    "house_number_end",
    "numbering_type",
    "location_class",
    "location_score",
    "source_page"
]

if df[required_columns].isna().any().any():
    raise ValueError("Missing required values. Ingestion cancelled.")

if not df["numbering_type"].isin(["U", "G", "S"]).all():
    raise ValueError("Invalid numbering types detected.")

if not df["location_class"].isin(["normal", "gut"]).all():
    raise ValueError("Invalid location classifications detected.")

duplicate_count = df.duplicated(
    subset=[
        "street",
        "house_number_start",
        "house_number_end",
        "numbering_type",
        "location_class"
    ]
).sum()

if duplicate_count > 0:
    raise ValueError(
        f"{duplicate_count} duplicate location keys found. "
        "Ingestion cancelled."
    )

print("Validation successful.")
print("Duplicate location keys: 0")


# --------------------------------------------------
# MYSQL INGESTION
# --------------------------------------------------

print("\nStarting MySQL ingestion...")

with engine.begin() as connection:

    existing_count = connection.execute(
        text("SELECT COUNT(*) FROM raw_residential_locations")
    ).scalar()

    if existing_count > 0:
        raise RuntimeError(
            f"Target table already contains {existing_count} rows. "
            "Ingestion stopped to prevent duplicates."
        )

    df.to_sql(
        name="raw_residential_locations",
        con=connection,
        if_exists="append",
        index=False,
        chunksize=1000,
        method="multi"
    )


# --------------------------------------------------
# FINAL VERIFICATION
# --------------------------------------------------

with engine.connect() as connection:

    mysql_count = connection.execute(
        text("SELECT COUNT(*) FROM raw_residential_locations")
    ).scalar()

print("\nFINAL INGESTION REPORT")
print("----------------------")
print(f"Extracted records: {len(df)}")
print(f"Skipped unmatched lines: {len(unmatched_lines)}")
print(f"MySQL records: {mysql_count}")

if mysql_count == len(df):
    print("\nSUCCESS: Residential location data loaded!")
else:
    raise RuntimeError("MySQL record count verification failed.")

engine.dispose()
