import os
import pymupdf
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from app.schemas import DocumentExtraction

# Load GEMINI_API_KEY from your .env file
load_dotenv()
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=25_000),
)

# Free-tier models ordered from lowest congestion/latency to highest
FALLBACK_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "gemini-3.6-flash",
    "gemini-3.8-flash",
]

SYSTEM_PROMPT = """
You are a precise bilingual (Japanese-English) financial and document extraction assistant.
Extract all fields accurately from the provided Japanese receipt, bill, or official notice.
- Keep original Japanese item names in `name_ja` and provide clear English translations in `name_en`.
- Extract every individual item price in JPY.
- If consumption tax (外税) is added separately at the bottom rather than included in item prices, put it in `tax_jpy`.
- If store discounts, coupons, or point redemptions (割引, 値引, クーポン, ポイント利用) appear on the receipt, put the total discount amount as a positive integer in `discount_jpy` (0 if none).
- Use YYYY-MM-DD format for `date_iso` if a date is visible.
"""


def _generate_with_fallback(contents: list) -> DocumentExtraction:
    """Tries each free-tier model in order if Google returns 503 (overloaded) or 429 (rate limit)."""
    last_error = None
    for model_name in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentExtraction,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            return DocumentExtraction.model_validate_json(response.text)
        except (errors.ServerError, errors.ClientError) as err:
            last_error = err
            print(f"[Fallback] {model_name} busy ({err.code}), trying next model...")
    raise RuntimeError(f"All fallback models failed. Last error: {last_error}")


def extract_from_image(file_bytes: bytes, mime_type: str) -> DocumentExtraction:
    """Extracts structured data directly from a receipt/document image (JPEG, PNG, WEBP)."""
    contents = [
        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
        SYSTEM_PROMPT,
    ]
    return _generate_with_fallback(contents)


def extract_from_pdf(file_bytes: bytes) -> DocumentExtraction:
    """Extracts text from a PDF using PyMuPDF, falling back to vision if it is a scanned PDF."""
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    extracted_text = "\n\n".join(page.get_text("text") for page in doc).strip()

    if len(extracted_text) > 30:
        contents = [f"{SYSTEM_PROMPT}\n\nDocument Text:\n{extracted_text}"]
    else:
        contents = [
            types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"),
            SYSTEM_PROMPT,
        ]
    return _generate_with_fallback(contents)