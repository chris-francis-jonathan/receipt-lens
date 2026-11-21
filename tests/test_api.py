import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app import database
from app.main import app
from app.schemas import DocumentExtraction, LineItem


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Redirects SQLite to a temporary test file so real data is never touched."""
    test_db_file = tmp_path / "test_receipt_lens.db"
    monkeypatch.setattr(database, "DB_PATH", test_db_file)
    return test_db_file


def make_sample_doc(total_amount_jpy: int = 149) -> DocumentExtraction:
    """Helper that builds a valid sample receipt for reuse across tests."""
    return DocumentExtraction(
        document_type="receipt",
        vendor_or_issuer="ライフ 松ヶ崎店",
        date_iso="2026-11-18",
        items=[LineItem(name_ja="ブロッコリー", name_en="Broccoli", price_jpy=138)],
        tax_jpy=11,
        total_amount_jpy=total_amount_jpy,
        category="groceries",
        english_summary="Purchased broccoli at Life supermarket.",
    )


# --- 1. PYDANTIC & DETERMINISTIC MATH TESTS ---


def test_schema_exact_math_sets_needs_review_false():
    doc = make_sample_doc(total_amount_jpy=149)  # 138 + 11 == 149
    assert doc.calculated_total_jpy == 149
    assert doc.needs_review is False


def test_schema_discount_mismatch_flags_needs_review():
    doc = make_sample_doc(total_amount_jpy=140)  # 138 + 11 == 149 != 140
    assert doc.calculated_total_jpy == 149
    assert doc.needs_review is True


def test_schema_rejects_negative_price():
    with pytest.raises(ValidationError):
        LineItem(name_ja="テスト", name_en="Test", price_jpy=-100)


# --- 2. SQLITE DATABASE TESTS ---


def test_database_crud_and_category_summary(isolated_db):
    grocery_id = database.insert_document(make_sample_doc(total_amount_jpy=140))

    utility_doc = DocumentExtraction(
        document_type="bill",
        vendor_or_issuer="関西電力",
        date_iso="2026-11-20",
        items=[],
        tax_jpy=0,
        total_amount_jpy=4200,
        category="utilities",
        english_summary="November electricity bill.",
        action_deadline="2026-12-05",
    )
    database.insert_document(utility_doc)

    # Verify summary groups and sorts highest spend first
    summary = database.get_category_summary()
    assert summary[0] == {
        "category": "utilities",
        "document_count": 1,
        "total_jpy": 4200,
    }
    assert summary[1] == {
        "category": "groceries",
        "document_count": 1,
        "total_jpy": 140,
    }

    # Verify marking a flagged receipt as reviewed
    assert database.mark_as_reviewed(grocery_id) is True
    docs = database.get_all_documents(category="groceries")
    assert len(docs) == 1
    assert docs[0]["needs_review"] is False

    # Verify deletion
    assert database.delete_document(grocery_id) is True
    assert database.get_all_documents(category="groceries") == []


# --- 3. FASTAPI ENDPOINT TESTS (WITH MOCKED GEMINI AI) ---


def test_upload_endpoint_saves_mocked_extraction(isolated_db, monkeypatch):
    def fake_extract_image(image_bytes: bytes, mime_type: str) -> DocumentExtraction:
        return make_sample_doc(total_amount_jpy=149)

    # Replace the real Gemini call with our instant fake function
    monkeypatch.setattr("app.main.extract_from_image", fake_extract_image)

    with TestClient(app) as client:
        response = client.post(
            "/documents/upload",
            files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == 1
        assert body["data"]["vendor_or_issuer"] == "ライフ 松ヶ崎店"
        assert body["data"]["needs_review"] is False

        # Verify GET /documents returns the saved record
        list_res = client.get("/documents")
        assert list_res.status_code == 200
        assert len(list_res.json()) == 1


def test_upload_rejects_unsupported_file_type(isolated_db):
    with TestClient(app) as client:
        response = client.post(
            "/documents/upload",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


def test_missing_document_returns_404(isolated_db):
    with TestClient(app) as client:
        patch_res = client.patch("/documents/999/review")
        delete_res = client.delete("/documents/999")
        assert patch_res.status_code == 404
        assert delete_res.status_code == 404