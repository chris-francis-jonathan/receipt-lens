# ReceiptLens — Bilingual Japanese-English Document & Receipt Analyzer

ReceiptLens is a full-stack financial and administrative document extraction pipeline built for international students and residents in Japan. It parses Japanese supermarket receipts, utility bills, and official PDF notices into structured bilingual (Japanese/English) JSON records, validates arithmetic consistency automatically, and stores categorized spending analytics in SQLite.

## Key Engineering Features

* **Strict Schema Enforcement (Pydantic v2):** Enforces typed extraction (`DocumentExtraction` & `LineItem`) using Gemini structured outputs, eliminating brittle regex parsing.
* **Deterministic Math Sanity Check:** Computes `calculated_total_jpy` from extracted line items plus consumption tax (`外税`) and flags discrepancies (`needs_review = True`) caused by store discounts, loyalty points, or OCR misreads for human verification.
* **Resilient Model Fallback Chain:** Automatically fails over across free-tier Gemini models (`gemini-3.6-flash` → `gemini-3.5-flash-lite` → `gemini-3.8-flash`) with bounded HTTP timeouts to handle `503`/`504` traffic spikes gracefully.
* **Hybrid PDF Processing:** Extracts embedded text locally via `PyMuPDF` for digital PDFs to minimize token usage and latency, falling back to multimodal vision parsing for scanned paper PDFs.
* **Vendor-Agnostic Architecture:** Isolates all LLM API calls inside `app/extractor.py`, keeping validation, database persistence, API routing, and UI layers decoupled from the underlying AI provider.

## Tech Stack

* **Language:** Python 3.13
* **AI & Document Parsing:** Google GenAI SDK (`google-genai`), PyMuPDF (`pymupdf`)
* **Validation & Backend:** Pydantic v2, FastAPI *(in progress)*
* **Database:** SQLite (`sqlite3` with parameterized queries) *(in progress)*
* **Frontend:** Streamlit *(planned)*

## Project Structure

```text
receipt-lens/
├── app/
│   ├── schemas.py       # Pydantic v2 models & computed math sanity checks
│   ├── extractor.py     # Multimodal image/PDF extraction & model fallback logic
│   ├── database.py      # SQLite persistence & spending aggregations (Next)
│   └── main.py          # FastAPI REST endpoints (Planned)
├── frontend/
│   └── dashboard.py     # Streamlit analytics & upload UI (Planned)
├── tests/               # Pytest unit & API integration tests (Planned)
├── BUILD_LOG.md         # Incremental development tracker
└── requirements.txt
```

## Local Setup

1. **Clone the repository and create a virtual environment:**
   ```bash
   git clone [https://github.com/](https://github.com/)chris-francis-jonathan/receipt-lens.git
   cd receipt-lens
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install pydantic google-genai pymupdf python-dotenv fastapi uvicorn streamlit
   ```

3. **Configure environment variables:**
   Create a `.env` file in the project root and add your free Google AI Studio key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

## Known Edge Cases & Roadmap

* **Discounts & Point Redemptions (v1.1):** Japanese supermarket receipts frequently apply line-item discounts (`値引`) or loyalty point deductions after subtotaling. Currently, these trigger `needs_review: true` safely; v1.1 will add a dedicated `discount_jpy` field.
* **FastAPI & Streamlit Integration:** Exposing REST endpoints and an interactive bilingual dashboard for receipt uploads and monthly category breakdowns.