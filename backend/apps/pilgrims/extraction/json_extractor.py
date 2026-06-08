from .ai_extractor import extract_structured_data


def extract_json_from_document(document):
    """Send a MedicalDocument's extracted_text to the AI extractor,
    save the resulting structured data to MedicalDocument.extracted_json,
    and return it.
    """
    structured_data = extract_structured_data(document.extracted_text)

    document.extracted_json = structured_data
    document.save(update_fields=["extracted_json", "updated_at"])
    return structured_data
