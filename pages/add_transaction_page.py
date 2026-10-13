# pages/add_transaction_page.py
import streamlit as st
from clients.b2_client import upload_to_b2
from clients.supabase_client import create_receipt, get_user_id
from clients.gemini_client import extract_receipt
from clients.currency_client import convert_to_php


CATEGORIES = [
    "Food & Groceries",
    "Transportation",
    "Housing & Utilities",
    "Academic & School",
    "Personal Care & Health",
    "Clothing & Accessories",
    "Communication & Tech",
    "Social & Leisure",
    "Travel & Exploration",
    "Administrative & Financial",
]
CURRENCIES = ["THB", "PHP", "IDR", "MYR"]

_FORM_KEYS = [
    "tx_merchant",
    "tx_or_number",
    "tx_category",
    "tx_currency",
    "tx_description",
    "tx_total_amount",
    "tx_text_context",
    "tx_image_context",
]


def _seed_form_defaults(extracted: dict | None) -> None:
    defaults = {
        "tx_merchant": "",
        "tx_or_number": "",
        "tx_category": "Food & Groceries",
        "tx_currency": "THB",
        "tx_description": "",
        "tx_total_amount": 0.0,
        "tx_text_context": "",
        "tx_image_context": "",
    }
    if extracted:
        defaults.update({
            "tx_merchant":      extracted.get("merchant") or "",
            "tx_or_number":     extracted.get("or_number") or "",
            "tx_category":      extracted.get("category") or "Food & Groceries",
            "tx_currency":      extracted.get("currency") or "THB",
            "tx_description":   extracted.get("description") or "",
            "tx_total_amount":  float(extracted.get("total_amount") or 0.0),
            "tx_text_context":  extracted.get("raw_text") or "",
            "tx_image_context": extracted.get("image_context") or "",
        })
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _reset_form_keys() -> None:
    for k in _FORM_KEYS:
        st.session_state.pop(k, None)


def add_transaction_page():
    st.title("Smart Receipt Entry")

    st.session_state.setdefault("tx_extracted", None)
    st.session_state.setdefault("tx_scan_bytes", None)
    st.session_state.setdefault("tx_scan_mime", None)
    st.session_state.setdefault("tx_upload_nonce", 0)

    st.subheader("1. Upload receipt")
    uploaded = st.file_uploader(
        "Receipt image",
        type=["jpg", "jpeg", "png", "pdf"],
        key=f"tx_upload_{st.session_state.tx_upload_nonce}",
    )

    scan_col, skip_col, clear_col = st.columns([1, 1, 1])

    with skip_col:
        skip_clicked = st.button(
            "Skip Processing",
            type="primary",
            use_container_width=True,
            disabled=uploaded is None,
        )

    with scan_col:
        scan_clicked = st.button(
            "Scan with Gemini",
            type="secondary",
            use_container_width=True,
            disabled=uploaded is None,
        )

    with clear_col:
        clear_clicked = st.button(
            "Clear scan",
            type="tertiary",
            use_container_width=True,
        )

    if clear_clicked:
        st.session_state.tx_extracted = None
        st.session_state.tx_scan_bytes = None
        st.session_state.tx_scan_mime = None
        _reset_form_keys()
        st.rerun()

    if skip_clicked and uploaded is not None:
        st.session_state.tx_extracted = None
        st.session_state.tx_scan_bytes = uploaded.getvalue()
        st.session_state.tx_scan_mime = uploaded.type or "image/jpeg"
        _reset_form_keys()
        st.rerun()

    if scan_clicked and uploaded is not None:
        image_bytes = uploaded.getvalue()
        mime = uploaded.type or "image/jpeg"
        with st.spinner("Scanning with Gemini..."):
            try:
                data = extract_receipt(image_bytes, mime)
                st.session_state.tx_extracted = data
                st.session_state.tx_scan_bytes = image_bytes
                st.session_state.tx_scan_mime = mime
                _reset_form_keys()
                st.rerun()
            except Exception as e:
                st.error(f"Extraction failed: {e}")

    if st.session_state.tx_extracted:
        with st.expander("Extracted fields (edit before saving)", expanded=False):
            st.json(st.session_state.tx_extracted)

    _seed_form_defaults(st.session_state.tx_extracted)

    st.subheader("2. Review & save")

    with st.form("receipt_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            merchant = st.text_input("Merchant Name", key="tx_merchant")
            or_number = st.text_input("OR / Invoice Number", key="tx_or_number")
            currency = st.selectbox(
                "Currency",
                CURRENCIES,
                key="tx_currency",
                index=CURRENCIES.index(
                    st.session_state.get("tx_currency", "THB")
                ),
            )
            category = st.selectbox(
                "Category",
                CATEGORIES,
                key="tx_category",
                index=CATEGORIES.index(
                    st.session_state.get("tx_category", "Food & Groceries")
                ),
            )
        with col2:
            txn_date = st.date_input("Transaction Date")
            doc_date = st.date_input("Documentation Date")
            total_amount = st.number_input(
                "Total Amount",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="tx_total_amount",
            )

        description = st.text_area("Description", key="tx_description")

        preview_bytes = st.session_state.tx_scan_bytes
        preview_mime = st.session_state.tx_scan_mime
        if preview_bytes:
            if preview_mime == "application/pdf":
                st.info("PDF attached (preview not shown).")
            else:
                st.image(
                    preview_bytes,
                    caption=uploaded.name if uploaded else "Scanned receipt",
                    use_container_width=True,
                )

        text_context = st.text_area(
            "Raw OCR text (optional)", key="tx_text_context"
        )
        image_context = st.text_area(
            "Image summary (optional)", key="tx_image_context"
        )

        submitted = st.form_submit_button(
            "Save Receipt", use_container_width=True
        )

    if not submitted:
        return

    image_bytes = st.session_state.tx_scan_bytes
    mime = st.session_state.tx_scan_mime
    filename = uploaded.name if uploaded else "receipt"

    if uploaded is not None:
        image_bytes = uploaded.getvalue()
        mime = uploaded.type or "image/jpeg"
        filename = uploaded.name

    if not image_bytes:
        st.error("Please attach the receipt image or scan one first.")
        return

    try:
        user_id = get_user_id()
    except ValueError:
        st.error("You must be logged in to save a receipt.")
        return

    try:
        b2_key = upload_to_b2(
            image_bytes,
            filename,
            user_id,
            content_type=mime,
        )
    except Exception as e:
        st.error(f"Image upload failed: {e}")
        return

    php_total_amount = convert_to_php(
        amount=total_amount,
        from_currency=currency,
        date=txn_date.isoformat(),
    )

    payload = {
        "merchant_id":        merchant.strip() or None,
        "or_number":          or_number.strip() or None,
        "category":           category,
        "description":        description.strip() or None,
        "transaction_date":   txn_date.isoformat(),
        "documentation_date": doc_date.isoformat(),
        "currency":           currency,
        "total_amount":       float(total_amount),
        "php_total_amount":   php_total_amount,
        "backblaze_image":    b2_key,
        "text_context":       text_context.strip() or None,
        "image_context":      image_context.strip() or None,
    }

    try:
        create_receipt(payload)
    except Exception as e:
        st.error(f"Receipt saved to storage but DB insert failed: {e}")
        return

    st.session_state.tx_upload_nonce += 1
    st.session_state.tx_extracted = None
    st.session_state.tx_scan_bytes = None
    st.session_state.tx_scan_mime = None

    st.success("Receipt saved.")
    st.rerun()