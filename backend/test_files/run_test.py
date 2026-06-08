"""Standalone script to manually test the full extraction pipeline
(raw text extraction + AI structured JSON extraction) on real sample files.

Run from the backend/ directory with:
    python test_files/run_test.py

Structured JSON results are also written to test_files/output/ as .json files.
"""
import json
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.pilgrims.extraction.ai_extractor import extract_structured_data  # noqa: E402
from apps.pilgrims.extraction.image_extractor import extract_text_from_image  # noqa: E402
from apps.pilgrims.extraction.pdf_extractor import extract_text_from_pdf  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PDF_PATH = os.path.join(BASE_DIR, "patient_abdullah_report.pdf")
IMAGE_PATH = os.path.join(BASE_DIR, "patient_fatima_prescription.jpg")


def show_text(label, file_path, text):
    print("=" * 60)
    print(f"{label}: {file_path}")
    print("-" * 60)
    print(text if text else "(no text extracted)")
    print("=" * 60)
    print()


def show_and_save_json(label, output_filename, structured_data):
    print("=" * 60)
    print(f"{label} -> structured JSON")
    print("-" * 60)
    pretty = json.dumps(structured_data, indent=2, ensure_ascii=False)
    print(pretty if structured_data is not None else "(AI extraction failed - see logs above)")
    print("=" * 60)
    print()

    if structured_data is not None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(pretty)
        print(f"Saved to: {output_path}\n")


def main():
    pdf_text = extract_text_from_pdf(PDF_PATH)
    show_text("PDF extraction", PDF_PATH, pdf_text)
    show_and_save_json("Abdullah's report", "abdullah_report_extracted.json", extract_structured_data(pdf_text))

    image_text = extract_text_from_image(IMAGE_PATH)
    show_text("Image OCR extraction", IMAGE_PATH, image_text)
    show_and_save_json("Fatima's prescription", "fatima_prescription_extracted.json", extract_structured_data(image_text))


if __name__ == "__main__":
    main()
