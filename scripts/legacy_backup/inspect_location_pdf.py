
import pdfplumber
from pathlib import Path

PDF_PATH = Path(
    r"C:\Users\athar\Downloads\d-wohnlagenverzeichnis-2025-data.pdf"
)

if not PDF_PATH.exists():
    raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

print("Opening PDF...")

with pdfplumber.open(PDF_PATH) as pdf:

    print("Total PDF pages:", len(pdf.pages))

    # Inspect first five pages
    for page_number, page in enumerate(pdf.pages[:5], start=1):

        print(f"\n{'=' * 50}")
        print(f"PAGE {page_number}")
        print("=" * 50)

        text = page.extract_text()

        if text:
            print(text[:5000])
        else:
            print("No text extracted from this page.")

print("\nPDF inspection completed.")
