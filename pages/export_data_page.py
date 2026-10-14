# pages/export_data_page.py
from datetime import datetime

import pandas as pd
import streamlit as st

from clients.supabase_client import list_receipts


ANY_CATEGORY = "All Categories"
ANY_CURRENCY = "All Currencies"


def export_data_page():
    st.title("Export Data")
    st.write(
        "Export your receipt data in CSV format. Useful for backups, "
        "spreadsheet analysis, or importing into other applications."
    )

    # ---- Load data once ----
    try:
        rows = list_receipts(order_by="transaction_date", desc=True)
    except Exception as e:
        st.error(f"Failed to load receipts: {e}")
        return

    if not rows:
        st.info("You have no receipts to export yet.")
        return

    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)

    # ---- Filters ----
    st.subheader("1. Choose what to export")
    with st.expander("Filters", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            min_date = df["transaction_date"].min().date()
            max_date = df["transaction_date"].max().date()
            date_range = st.date_input(
                "Transaction date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="export_date_range",
            )

            categories = sorted(df["category"].dropna().unique().tolist())
            picked_category = st.selectbox(
                "Category",
                options=[ANY_CATEGORY] + categories,
                index=0,
                key="export_category",
            )

        with col2:
            currencies = sorted(df["currency"].dropna().unique().tolist())
            picked_currency = st.selectbox(
                "Currency",
                options=[ANY_CURRENCY] + currencies,
                index=0,
                key="export_currency",
            )

            include_blobs = st.checkbox(
                "Include image / OCR text columns",
                value=False,
                help=(
                    "These columns (text_context, image_context) can be very "
                    "long. Leave off for a compact spreadsheet."
                ),
                key="export_include_blobs",
            )

    # Normalize date_range — Streamlit returns a tuple, but sometimes a single date
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    # ---- Apply filters ----
    mask = (
        (df["transaction_date"].dt.date >= start_date)
        & (df["transaction_date"].dt.date <= end_date)
    )
    if picked_category != ANY_CATEGORY:
        mask &= df["category"] == picked_category
    if picked_currency != ANY_CURRENCY:
        mask &= df["currency"] == picked_currency

    filtered = df.loc[mask].copy()

    # ---- Preview ----
    st.subheader("2. Preview")
    st.caption(f"**{len(filtered)}** of **{len(df)}** receipts match your filters.")

    if filtered.empty:
        st.warning("No receipts match the current filters.")
        return

    preview_cols = [
        c for c in [
            "transaction_date", "merchant_id", "category",
            "currency", "total_amount", "or_number",
        ] if c in filtered.columns
    ]
    preview = filtered[preview_cols].copy()
    preview["transaction_date"] = preview["transaction_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(preview, use_container_width=True, hide_index=True)

    # ---- Build CSV ----
    st.subheader("3. Download")

    export_df = filtered.copy()
    if not include_blobs:
        export_df = export_df.drop(
            columns=[c for c in ("text_context", "image_context") if c in export_df],
            errors="ignore",
        )

    for col in ("transaction_date", "documentation_date", "created_at", "updated_at"):
        if col in export_df.columns:
            export_df[col] = export_df[col].astype(str).replace("NaT", "")

    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")

    # Smart filename: include category/currency only when a specific one is chosen
    parts = [f"{start_date:%Y%m%d}"]
    if start_date != end_date:
        parts.append(f"{end_date:%Y%m%d}")
    if picked_category != ANY_CATEGORY:
        parts.append(picked_category.lower().replace(" ", "_"))
    if picked_currency != ANY_CURRENCY:
        parts.append(picked_currency.lower())
    default_name = "receipts_" + "_".join(parts)

    colA, colB = st.columns([1, 1])
    with colA:
        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name=f"{default_name}.csv",
            mime="text/csv",
            use_container_width=True,
            key="export_download_csv",
        )
    with colB:
        if st.button(
            "Reload from database",
            use_container_width=True,
            key="export_reload",
        ):
            st.rerun()

    st.caption(
        f"Exported on {datetime.now():%Y-%m-%d %H:%M}. "
        f"Columns: {', '.join(export_df.columns)}."
    )