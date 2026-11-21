# ReceiptLens — Architecture & Contracts

## 1. Repository Layout
```text
receipt-lens/
├── app/
│   ├── __init__.py
│   ├── schemas.py        # Pydantic models, Literal enums, deterministic math checks
│   ├── extractor.py      # Gemini multimodal/PDF extractor with model fallback
│   ├── database.py       # SQLite persistence & category aggregation queries
│   └── main.py           # FastAPI REST endpoints & file upload validation
├── frontend/
│   └── dashboard.py      # Streamlit UI (communicates strictly via FastAPI HTTP)
├── tests/
│   └── test_api.py       # Pytest unit & integration tests (isolated tmp_path DB)
├── .env.example          # Environment variable template
├── .gitignore            # Ignores .venv, .env, *.db, __pycache__
├── ARCHITECTURE.md       # System contracts & conventions (this file)
├── BUILD_LOG.md          # Step-by-step milestone checklist
├── README.md             # Public setup & usage guide
└── requirements.txt      # Top-level Python dependencies
```

---

## 2. Data Schema Contracts (`app/schemas.py`)

* **`CategoryType` (`Literal`):** `"groceries"`, `"dining"`, `"utilities"`, `"university"`, `"rent"`, `"transport"`, `"other"`
* **`LineItem` (`BaseModel`):**
  * `name_ja: str` — Original Japanese item name
  * `name_en: str` — Concise English translation
  * `price_jpy: int` (`ge=0`) — Item price in JPY
* **`DocumentExtraction` (`BaseModel`):**
  * `document_type: Literal["receipt", "bill", "official_notice", "other"]`
  * `vendor_or_issuer: str`
  * `date_iso: Optional[str] = None` (`YYYY-MM-DD`)
  * `items: list[LineItem] = []`
  * `tax_jpy: int = 0` (`ge=0`) — Separate consumption tax (外税)
  * `total_amount_jpy: int` (`ge=0`) — Printed grand total in JPY
  * `category: CategoryType`
  * `english_summary: str`
  * `action_deadline: Optional[str] = None`
  * **`calculated_total_jpy` (`@computed_field`):** `sum(item.price_jpy for item in self.items) + self.tax_jpy`
  * **`needs_review` (`@computed_field`):** `False` if `items` is empty; otherwise `calculated_total_jpy != total_amount_jpy`

---

## 3. AI Extraction Pipeline (`app/extractor.py`)

* **Client Configuration:** `google.genai.Client` with `timeout=25_000` ms (`25s`) and `thinking_config=types.ThinkingConfig(thinking_level="low")`.
* **Model Fallback Chain (`FALLBACK_MODELS`):**
  1. `os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")`
  2. `"gemini-3.6-flash"`
  3. `"gemini-3.8-flash"`
* **PDF Routing Heuristic:** Extracts text via `pymupdf`. If `len(extracted_text) > 30`, sends text prompt; otherwise sends raw `application/pdf` bytes for multimodal vision extraction.

---

## 4. SQLite Persistence (`app/database.py` → `receipt_lens.db`)

Table `documents` columns:
`id` (PK), `created_at` (UTC ISO), `document_type`, `vendor_or_issuer`, `date_iso`, `tax_jpy`, `total_amount_jpy`, `calculated_total_jpy`, `needs_review` (`0`/`1`), `category`, `english_summary`, `action_deadline`, `items_json` (JSON-serialized `list[LineItem]`).

---

## 5. FastAPI Endpoints (`app/main.py`)

* `GET /health` → `{"status": "ok", "service": "receipt-lens"}`
* `POST /documents/upload` (`201`) → Accepts `image/jpeg`, `image/png`, `image/webp`, `application/pdf`; extracts & inserts into SQLite
* `GET /documents?category=...` → Returns saved records (newest first)
* `GET /documents/summary` → Returns `[{"category", "document_count", "total_jpy"}]` ordered by `total_jpy DESC`
* `PATCH /documents/{doc_id}/review` → Sets `needs_review = 0` (`404` if missing)
* `DELETE /documents/{doc_id}` → Deletes row by ID (`404` if missing)

---

## 6. Project Conventions

* **Commits:** Conventional Commits in imperative mood (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
* **`BUILD_LOG.md` Format:** `- [x] **Step N:** Description`
* **Local-Only Files:** Personal notes (`STUDY_NOTES.md`) excluded via `.git/info/exclude`; runtime database (`receipt_lens.db`) and secrets (`.env`) ignored via `.gitignore`.