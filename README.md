# ReceiptLens

Bilingual Japanese-to-English receipt and document analyzer built with **FastAPI**, **Google Gemini (`google-genai`)**, **Pydantic**, **SQLite**, and **Streamlit**.

ReceiptLens extracts structured line items, Japanese-to-English translations, tax amounts, categories, and action deadlines from Japanese receipts (`JPEG`, `PNG`, `WEBP`) and digital PDFs (e.g., municipal notices, utility bills), verifies extracted arithmetic deterministically, and tracks spending by category.

---

## Architecture

```text
Streamlit UI (frontend/dashboard.py)
       │  HTTP (JSON / multipart upload)
       ▼
FastAPI REST API (app/main.py)
       ├──► Gemini Extractor (app/extractor.py) ──► Pydantic Validation (app/schemas.py)
       └──► SQLite Persistence (app/database.py) ──► receipt_lens.db
```

### Key Engineering Decisions
* **Deterministic Math Guardrail (`app/schemas.py`):** LLMs frequently miscalculate totals when store discounts or point deductions appear on receipts. Pydantic computes `calculated_total_jpy` (`sum(items) + tax_jpy`) in Python and automatically flags `needs_review = True` whenever line items are present and the sum differs from the printed receipt total.
* **Resilient Model Fallback (`app/extractor.py`):** Configured with a 25-second timeout, `thinking_level="low"`, and an automatic fallback chain (`gemini-3.5-flash-lite` → `gemini-3.6-flash` → `gemini-3.8-flash`) to handle transient rate limits or server timeouts gracefully.
* **Hybrid PDF Handling (`app/extractor.py`):** Uses PyMuPDF (`pymupdf`) to extract embedded text directly from digital PDFs before falling back to multimodal vision processing for scanned documents.
* **Decoupled Backend & Frontend (`app/main.py` & `frontend/dashboard.py`):** Business logic and SQLite persistence live behind RESTful FastAPI endpoints, keeping the UI independent and allowing automated API testing.

---

## Quickstart

### 1. Clone & Set Up Virtual Environment
```bash
git clone [https://github.com/chris-francis-jonathan/receipt-lens.git](https://github.com/chris-francis-jonathan/receipt-lens.git)
cd receipt-lens
python -m venv .venv
```

Activate the virtual environment:
* **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
* **macOS / Linux:** `source .venv/bin/activate`

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and add your Gemini API key:
```bash
cp .env.example .env
```
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Run the Application (Two Terminals)
**Terminal 1 — Start the FastAPI backend:**
```bash
uvicorn app.main:app --reload
```
*(Interactive Swagger API docs are available at `http://127.0.0.1:8000/docs`.)*

**Terminal 2 — Start the Streamlit dashboard:**
```bash
streamlit run frontend/dashboard.py
```
*(Open `http://localhost:8501` in your browser.)*

---

## Running Automated Tests

The `pytest` suite isolates SQLite using temporary directories (`tmp_path`) and mocks Gemini API calls so tests run offline in under a second:

```bash
python -m pytest -v
```