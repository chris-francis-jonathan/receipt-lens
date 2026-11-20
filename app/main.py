from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, File, HTTPException, UploadFile
from app.database import (
    delete_document,
    get_all_documents,
    get_category_summary,
    init_db,
    insert_document,
    mark_as_reviewed,
)
from app.extractor import extract_from_image, extract_from_pdf

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes the SQLite database table when the server starts."""
    init_db()
    yield


app = FastAPI(
    title="ReceiptLens API",
    description="Bilingual Japanese-English receipt and document extraction backend.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check() -> dict:
    """Simple endpoint to verify that the API server is running."""
    return {"status": "ok", "service": "receipt-lens"}


@app.post("/documents/upload", status_code=201)
def upload_document(file: UploadFile = File(...)) -> dict:
    """Uploads an image or PDF, extracts structured JSON, and saves it to SQLite."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Upload JPEG, PNG, WEBP, or PDF.",
        )

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        if file.content_type == "application/pdf":
            extracted = extract_from_pdf(file_bytes)
        else:
            extracted = extract_from_image(file_bytes, file.content_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Unexpected extraction error: {exc}"
        ) from exc

    doc_id = insert_document(extracted)
    return {
        "id": doc_id,
        "filename": file.filename,
        "data": extracted.model_dump(),
    }


@app.get("/documents")
def list_documents(category: Optional[str] = None) -> list[dict]:
    """Returns all saved documents, optionally filtered by ?category=..."""
    return get_all_documents(category=category)


@app.get("/documents/summary")
def category_summary() -> list[dict]:
    """Returns total JPY spent and receipt count grouped by category."""
    return get_category_summary()


@app.patch("/documents/{doc_id}/review")
def review_document(doc_id: int) -> dict:
    """Clears the needs_review flag on a specific document."""
    updated = mark_as_reviewed(doc_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return {"id": doc_id, "needs_review": False}


@app.delete("/documents/{doc_id}")
def remove_document(doc_id: int) -> dict:
    """Deletes a specific document from SQLite by its ID."""
    deleted = delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return {"deleted": True, "id": doc_id}