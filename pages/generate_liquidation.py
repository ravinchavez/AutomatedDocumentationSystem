import math
from datetime import date, datetime

import pandas as pd
import streamlit as st

from clients.b2_client import presigned_url
from clients.pdf_client import build_liquidation_pdf
from clients.supabase_client import list_receipts


ANY_CATEGORY = "All Categories"
ANY_CURRENCY = "All Currencies"


def _clean(rows: list[dict]) -> list[dict]:
    def _v(v):
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if hasattr(v, "isoformat") and not isinstance(v, str):
            try:
                return v.isoformat()
            except Exception:
                return None
        return v

    return [{k: _v(v) for k, v in r.items()} for r in rows]


def generate_liquidation_page():
    st.title("Generate Liquidation")
    st.write(
        "Generate a liquidation report based on your receipt data for financial reporting."
    )

    try:
        rows = list_receipts(order_by="transaction_date", desc=True)
    except Exception as e:
        st.error(f"Failed to load receipts: {e}")
        return

    if not rows:
        st.info("You have no receipts to include in a report yet.")
        return

    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)

    user_email = getattr(st.session_state.get("user"), "email", "")

    st.subheader("1. Report options")
    with st.expander("Filters and content", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            min_date = df["transaction_date"].min().date()
            max_date = df["transaction_date"].max().date()
            date_range = st.date_input(
                "Transaction date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="liq_date_range",
            )

            categories = sorted(df["category"].dropna().unique().tolist())
            picked_category = st.selectbox(
                "Category",
                options=[ANY_CATEGORY] + categories,
                index=0,
                key="liq_category",
            )

        with col2:
            currencies = sorted(df["currency"].dropna().unique().tolist())
            picked_currency = st.selectbox(
                "Currency",
                options=[ANY_CURRENCY] + currencies,
                index=0,
                key="liq_currency",
            )

            include_images = st.checkbox(
                "Include receipt images in the PDF",
                value=True,
                help=(
                    "Embedding images makes the PDF much larger and slower "
                    "to build. Turn off for a text-only report."
                ),
                key="liq_include_images",
            )

        title = st.text_input(
            "Report title",
            value="Liquidation Report",
            key="liq_title",
        )
        notes = st.text_area(
            "Notes (optional)",
            placeholder="e.g. April 2026 field work, submitted to Finance",
            key="liq_notes",
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    mask = (
        (df["transaction_date"].dt.date >= start_date)
        & (df["transaction_date"].dt.date <= end_date)
    )
    if picked_category != ANY_CATEGORY:
        mask &= df["category"] == picked_category
    if picked_currency != ANY_CURRENCY:
        mask &= df["currency"] == picked_currency

    filtered = df.loc[mask].copy().sort_values("transaction_date")
    filtered_rows = _clean(filtered.to_dict(orient="records"))

    st.subheader("2. Preview")
    if not filtered_rows:
        st.warning("No receipts match the current filters.")
        return

    total = float(filtered["total_amount"].sum())
    dominant_ccy = (
        filtered["currency"].mode().iloc[0]
        if not filtered["currency"].dropna().empty else "-"
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Receipts", len(filtered_rows))
    c2.metric("Total", f"{dominant_ccy} {total:,.2f}")
    c3.metric("Images included", "Yes" if include_images else "No")

    preview_cols = [
        c for c in [
            "transaction_date", "merchant", "category",
            "currency", "total_amount", "or_number",
        ] if c in filtered.columns
    ]
    preview = filtered[preview_cols].copy()
    preview["transaction_date"] = preview["transaction_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(preview, use_container_width=True, hide_index=True)

    st.subheader("3. Generate and download")
    if st.button(
        "Generate PDF",
        type="primary",
        use_container_width=True,
        key="liq_generate",
    ):
        with st.spinner("Building liquidation report..."):
            try:
                pdf_bytes = build_liquidation_pdf(
                    receipts=filtered_rows,
                    user_email=user_email,
                    image_url_resolver=presigned_url,
                    title=title or "Liquidation Report",
                    include_images=include_images,
                    notes=notes or "",
                )
                st.session_state["liq_pdf_bytes"] = pdf_bytes
            except Exception as e:
                st.error(f"Failed to generate PDF: {e}")
                return

    pdf_bytes = st.session_state.get("liq_pdf_bytes")
    if pdf_bytes:
        parts = [f"{start_date:%Y%m%d}"]
        if start_date != end_date:
            parts.append(f"{end_date:%Y%m%d}")
        if picked_category != ANY_CATEGORY:
            parts.append(picked_category.lower().replace(" ", "_"))
        if picked_currency != ANY_CURRENCY:
            parts.append(picked_currency.lower())
        fname = "liquidation_" + "_".join(parts) + ".pdf"

        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            use_container_width=True,
            key="liq_download",
        )
        st.caption(
            f"PDF generated at {datetime.now():%Y-%m-%d %H:%M}. "
            f"Size: {len(pdf_bytes) / 1024:.0f} KB."
        )