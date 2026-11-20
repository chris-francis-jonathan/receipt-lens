import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from app.schemas import DocumentExtraction

# Database file saved in the project root (ignored by Git via *.db in .gitignore)
DB_PATH = Path("receipt_lens.db")


def get_connection() -> sqlite3.Connection:
    """Opens a connection to the SQLite database with dict-like row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates the documents table if it does not already exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                document_type TEXT NOT NULL,
                vendor_or_issuer TEXT NOT NULL,
                date_iso TEXT,
                tax_jpy INTEGER NOT NULL DEFAULT 0,
                total_amount_jpy INTEGER NOT NULL,
                calculated_total_jpy INTEGER NOT NULL,
                needs_review INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL,
                english_summary TEXT NOT NULL,
                action_deadline TEXT,
                items_json TEXT NOT NULL
            )
            """
        )


def insert_document(doc: DocumentExtraction) -> int:
    """Saves a validated DocumentExtraction object and returns its new row ID."""
    init_db()
    created_at = datetime.now(timezone.utc).isoformat()
    items_json = json.dumps(
        [item.model_dump() for item in doc.items],
        ensure_ascii=False,
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO documents (
                created_at, document_type, vendor_or_issuer, date_iso,
                tax_jpy, total_amount_jpy, calculated_total_jpy, needs_review,
                category, english_summary, action_deadline, items_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                doc.document_type,
                doc.vendor_or_issuer,
                doc.date_iso,
                doc.tax_jpy,
                doc.total_amount_jpy,
                doc.calculated_total_jpy,
                int(doc.needs_review),
                doc.category,
                doc.english_summary,
                doc.action_deadline,
                items_json,
            ),
        )
        return cursor.lastrowid


def get_all_documents(category: Optional[str] = None) -> list[dict]:
    """Fetches all stored documents (newest first), optionally filtered by category."""
    init_db()
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM documents WHERE category = ? ORDER BY id DESC",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY id DESC"
            ).fetchall()

    results = []
    for row in rows:
        record = dict(row)
        record["needs_review"] = bool(record["needs_review"])
        record["items"] = json.loads(record.pop("items_json"))
        results.append(record)
    return results


def get_category_summary() -> list[dict]:
    """Calculates total JPY spent and document count per spending category."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                category,
                COUNT(*) AS document_count,
                SUM(total_amount_jpy) AS total_jpy
            FROM documents
            GROUP BY category
            ORDER BY total_jpy DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def mark_as_reviewed(doc_id: int) -> bool:
    """Clears the needs_review warning flag after a user verifies a receipt."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE documents SET needs_review = 0 WHERE id = ?",
            (doc_id,),
        )
        return cursor.rowcount > 0


def delete_document(doc_id: int) -> bool:
    """Deletes a document by ID and returns True if a row was removed."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM documents WHERE id = ?",
            (doc_id,),
        )
        return cursor.rowcount > 0