import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="ReceiptLens — Bilingual Receipt Analyzer",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 ReceiptLens")
st.caption("Bilingual Japanese-English Receipt & Document Analyzer")


def is_backend_online() -> bool:
    """Checks if the FastAPI server is running before making API calls."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


if not is_backend_online():
    st.error(
        "FastAPI backend is offline. Open a second terminal, activate `.venv`, "
        "and run: `uvicorn app.main:app --reload`"
    )
    st.stop()


# --- SIDEBAR: UPLOAD NEW DOCUMENT ---
with st.sidebar:
    st.header("📤 Upload Document")
    uploaded_file = st.file_uploader(
        "Choose a Japanese receipt or PDF notice",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
    )

    if uploaded_file is not None:
        if uploaded_file.type.startswith("image/"):
            st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)

        if st.button("Extract & Save", type="primary", use_container_width=True):
            with st.spinner("Scanning document with Gemini AI..."):
                files = {
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type,
                    )
                }
                try:
                    res = requests.post(
                        f"{API_BASE_URL}/documents/upload",
                        files=files,
                        timeout=60,
                    )
                    if res.status_code == 201:
                        st.session_state["last_upload"] = res.json()
                        st.success("Saved to database!")
                    else:
                        detail = res.json().get("detail", res.text)
                        st.error(f"Upload failed ({res.status_code}): {detail}")
                except requests.RequestException as exc:
                    st.error(f"Connection error: {exc}")


# --- SHOW LATEST EXTRACTION RESULT (IF ANY) ---
if "last_upload" in st.session_state:
    latest = st.session_state["last_upload"]["data"]
    st.subheader(f"Latest Scan: {latest['vendor_or_issuer']}")

    if latest["needs_review"]:
        st.warning(
            f"⚠️ Math Mismatch Detected: Items + tax - discount equal "
            f"¥{latest['calculated_total_jpy']:,}, but receipt total is "
            f"¥{latest['total_amount_jpy']:,}."
        )

    st.info(f"**Summary:** {latest['english_summary']}")
    if latest["items"]:
        st.dataframe(latest["items"], use_container_width=True, hide_index=True)
    st.divider()


# --- FETCH STORED DATA FROM FASTAPI ---
documents = requests.get(f"{API_BASE_URL}/documents", timeout=5).json()
summary = requests.get(f"{API_BASE_URL}/documents/summary", timeout=5).json()


# --- TOP METRICS & SPENDING ANALYTICS ---
total_spent = sum(doc["total_amount_jpy"] for doc in documents)
review_count = sum(1 for doc in documents if doc["needs_review"])

col1, col2, col3 = st.columns(3)
col1.metric("Total Tracked Spending", f"¥{total_spent:,}")
col2.metric("Saved Documents", len(documents))
col3.metric("Needs Review", review_count)

if summary:
    st.subheader("📊 Spending by Category")
    chart_col, table_col = st.columns([2, 1])
    with chart_col:
        st.bar_chart(summary, x="category", y="total_jpy")
    with table_col:
        st.dataframe(summary, use_container_width=True, hide_index=True)

st.divider()


# --- DOCUMENT HISTORY & ACTIONS ---
st.subheader("🗂️ Saved Documents")

categories = ["All"] + sorted({doc["category"] for doc in documents})
selected_category = st.selectbox("Filter by category", categories)

filtered_docs = (
    documents
    if selected_category == "All"
    else [doc for doc in documents if doc["category"] == selected_category]
)

if not filtered_docs:
    st.write("No documents found. Upload a receipt in the sidebar to get started.")
else:
    for doc in filtered_docs:
        badge = "⚠️ Needs Review" if doc["needs_review"] else "✅ Verified"
        date_label = doc["date_iso"] or "No date"
        header = (
            f"#{doc['id']} | {doc['vendor_or_issuer']} ({date_label}) — "
            f"¥{doc['total_amount_jpy']:,} [{doc['category']}] • {badge}"
        )

        with st.expander(header):
            st.write(f"**Summary:** {doc['english_summary']}")
            if doc["action_deadline"]:
                st.write(f"**Action Deadline:** {doc['action_deadline']}")

            st.write(
                f"**Tax:** ¥{doc['tax_jpy']:,} | "
                f"**Discount:** -¥{doc.get('discount_jpy', 0):,} | "
                f"**Calculated Total:** ¥{doc['calculated_total_jpy']:,} | "
                f"**Receipt Total:** ¥{doc['total_amount_jpy']:,}"
            )

            if doc["items"]:
                st.dataframe(doc["items"], use_container_width=True, hide_index=True)

            btn_col1, btn_col2, _ = st.columns([1, 1, 4])
            if doc["needs_review"]:
                if btn_col1.button("Mark as Reviewed", key=f"review_{doc['id']}"):
                    requests.patch(
                        f"{API_BASE_URL}/documents/{doc['id']}/review", timeout=5
                    )
                    st.rerun()

            if btn_col2.button("Delete", key=f"delete_{doc['id']}"):
                requests.delete(f"{API_BASE_URL}/documents/{doc['id']}", timeout=5)
                st.rerun()