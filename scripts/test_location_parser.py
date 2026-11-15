
import re
from pathlib import Path
import pdfplumber

PDF_PATH = Path(
    r"C:\Users\athar\Downloads\d-wohnlagenverzeichnis-2025-data.pdf"
)

# Match a complete residential location record
pattern = re.compile(
    r"^(.*?)\s+(\d+[a-zA-Z]?)\s*-\s*"
    r"(\d+[a-zA-Z]?)\s+([UGS])\s+"
    r"(normal|gut)\s+([\d,]+)$"
)

total_extracted = 0
total_unmatched = 0

with pdfplumber.open(PDF_PATH) as pdf:

    # PDF pages 3 to 7 contain actual records
    for page_index in range(2, 7):

        page = pdf.pages[page_index]
        lines = (page.extract_text() or "").splitlines()

        print(f"\nPDF Page: {page_index + 1}")

        for line in lines:

            match = pattern.match(line.strip())

            if match:
                street, start, end, number_type, location, score = (
                    match.groups()
                )

                score = float(score.replace(",", "."))

                print({
                    "street": street,
                    "house_start": start,
                    "house_end": end,
                    "numbering_type": number_type,
                    "location_class": location,
                    "score": score
                })

                total_extracted += 1

            elif (
                "Hausnummer" not in line
                and "Hamburger Wohnlagenverzeichnis" not in line
                and "ungerade" not in line
            ):
                if line.strip():
                    total_unmatched += 1

print("\n========== EXTRACTION TEST ==========")
print("Records extracted:", total_extracted)
print("Unmatched lines:", total_unmatched)
